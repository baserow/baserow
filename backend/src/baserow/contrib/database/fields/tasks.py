import itertools
import time
import traceback
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Optional, Type
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.db.models import OuterRef, Q, QuerySet, Subquery

from celery import chord, group
from loguru import logger
from opentelemetry import trace

from baserow.celery_singleton_backend import SingletonAutoRescheduleFlag
from baserow.config.celery import app
from baserow.contrib.database.fields.periodic_field_update_handler import (
    PeriodicFieldUpdateHandler,
)
from baserow.contrib.database.fields.registries import FieldType, field_type_registry
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.table.models import RichTextFieldMention
from baserow.contrib.database.views.handler import ViewSubscriptionHandler
from baserow.contrib.database.views.models import View, ViewSubscription
from baserow.core.models import Workspace
from baserow.core.telemetry.utils import add_baserow_trace_attrs, baserow_trace

tracer = trace.get_tracer(__name__)

# Workspaces that take longer than this are logged by id so we can look into them.
SLOW_WORKSPACE_LOG_THRESHOLD_SECONDS = 60

# How long one batch of workspaces may run. Batches run in parallel, so a slow one no
# longer holds up the rest and this no longer has to fit the run interval.
BATCH_UPDATE_SOFT_TIME_LIMIT = settings.PERIODIC_FIELD_UPDATE_TIMEOUT_MINUTES * 60
# Give the hard kill a small margin over the soft limit.
BATCH_UPDATE_HARD_TIME_LIMIT = BATCH_UPDATE_SOFT_TIME_LIMIT + 30

# Only one periodic-field cycle runs at a time. The parent acquires this Redis flag
# (fenced by the run's token) and the chord callback releases it. The TTL is the crash
# backstop; batches heartbeat it so a serialized cycle can't expire mid-flight.
RUN_LOCK_KEY = "periodic_fields_update_running"
RUN_LOCK_TTL = BATCH_UPDATE_HARD_TIME_LIMIT + 60


def filter_distinct_workspace_ids_per_fields(
    queryset: QuerySet, workspace_id: Optional[int] = None
) -> QuerySet:
    """
    Filters the provided queryset to only return the distinct workspace ids.

    :param queryset: The queryset that should be filtered.
    :param workspace_id: The id of the workspace that should be filtered on.
    """

    queryset = Workspace.objects.filter(
        application__database__table__field__in=queryset,
        application__trashed=False,
        application__database__table__trashed=False,
    )
    if workspace_id is not None:
        queryset = queryset.filter(id=workspace_id)
    # Ordering is applied later on the final workspace queryset; the ids collected here
    # go straight into a set, so any ordering at this stage is wasted work.
    return queryset.distinct().order_by()


@app.task(
    bind=True,
    queue=settings.PERIODIC_FIELD_UPDATE_QUEUE_NAME,
    soft_time_limit=settings.PERIODIC_FIELD_UPDATE_TIMEOUT_MINUTES * 60,
    time_limit=settings.PERIODIC_FIELD_UPDATE_TIMEOUT_MINUTES * 60 + 30,
)
def run_periodic_fields_updates(
    self,
    workspace_id: Optional[int] = None,
    update_now: bool = True,
    dispatch: bool = True,
):
    """
    Finds the workspaces whose periodic fields need refreshing and splits them across
    ``BASEROW_PERIODIC_FIELD_UPDATE_BATCH_COUNT`` tasks, so no single task has to update
    the whole instance at once. The count defaults to 1 (one task, like the old job) and
    can be raised to spread the work across more workers. When ``dispatch`` is False the
    updates run inline instead of being queued, which the management command uses to run
    synchronously.
    """

    workspace_ids = _collect_workspace_ids_needing_update(workspace_id)
    # Update the most out-of-date workspaces (oldest `now`) first, like the old job did,
    # so if there's a backlog the most overdue ones still get done first.
    ordered_ids = list(
        Workspace.objects.filter(id__in=workspace_ids)
        .order_by("now")
        .values_list("id", flat=True)
    )

    if not dispatch:
        for wid in ordered_ids:
            _update_workspace_periodic_fields(wid, update_now)
        return

    if not ordered_ids:
        return

    # One cycle at a time. Acquire the fenced run lock; skip if a cycle is still running.
    token = self.request.id or uuid4().hex
    flag = SingletonAutoRescheduleFlag(RUN_LOCK_KEY, timeout=RUN_LOCK_TTL)
    if not flag.acquire(token):
        # Warn (not info) so operators can see the overlap: a cycle is taking longer
        # than the gap between runs, so this one is skipped. Give more time between
        # runs (BASEROW_PERIODIC_FIELD_UPDATE_CRONTAB) or spread the work across more
        # tasks (BASEROW_PERIODIC_FIELD_UPDATE_BATCH_COUNT) so each cycle finishes first.
        logger.warning(
            "run_periodic_fields_updates skipped: the previous cycle is still running. "
            "Increase the interval between runs "
            "(BASEROW_PERIODIC_FIELD_UPDATE_CRONTAB) or the batch count "
            "(BASEROW_PERIODIC_FIELD_UPDATE_BATCH_COUNT) so a cycle finishes before the "
            "next one starts."
        )
        return

    try:
        batch_count = max(1, settings.PERIODIC_FIELD_UPDATE_BATCH_COUNT)
        batch_size = ceil(len(ordered_ids) / batch_count)
        batches = list(itertools.batched(ordered_ids, batch_size))
        header = group(
            update_workspaces_periodic_fields.s(
                list(batch_ids),
                update_now,
                batch_index=batch_index,
                run_token=token,
            )
            for batch_index, batch_ids in enumerate(batches)
        )
        chord(header)(finish_periodic_fields_update.si(token))
    except Exception:
        flag.clear_if(token)
        raise

    logger.info(
        "run_periodic_fields_updates dispatched {count} workspace(s) across "
        "{batches} batch(es).",
        count=len(ordered_ids),
        batches=len(batches),
    )


def _collect_workspace_ids_needing_update(
    workspace_id: Optional[int] = None,
) -> set[int]:
    """Returns the ids of workspaces that have at least one periodic field due."""

    # We pick the workspaces to update once here, before any of them are refreshed.
    # Only formula fields update periodically today, so this matches the old behaviour.
    # If another field type ever needs periodic updates, revisit this.
    workspace_ids: set[int] = set()
    for field_type_instance in field_type_registry.get_all():
        field_qs = field_type_instance.get_fields_needing_periodic_update()
        if field_qs is None:
            continue

        recently_used_workspace_ids = (
            PeriodicFieldUpdateHandler.get_recently_used_workspace_ids()
        )
        now = datetime.now(tz=timezone.utc)
        threshold = now - timedelta(
            minutes=settings.BASEROW_PERIODIC_FIELD_UPDATE_UNUSED_WORKSPACE_INTERVAL_MIN
        )
        workspaces = filter_distinct_workspace_ids_per_fields(
            field_qs, workspace_id
        ).filter(
            Q(id__in=recently_used_workspace_ids)
            | Q(now__lte=threshold)
            | Q(now__isnull=True)
        )
        workspace_ids.update(workspaces.values_list("id", flat=True))
    return workspace_ids


@baserow_trace(tracer)
def _run_periodic_field_type_update_per_workspace(
    field_type_instance: Type[FieldType], workspace: Workspace, update_now: bool = True
):
    qs = field_type_instance.get_fields_needing_periodic_update()
    if qs is None:
        return

    if update_now:
        workspace.refresh_now()
    add_baserow_trace_attrs(update_now=update_now, workspace_id=workspace.id)

    fields = (
        qs.filter(
            table__database__workspace_id=workspace.id,
            table__database__trashed=False,
            table__trashed=False,
        )
        .select_related("table")
        .order_by("table__database_id")
    )

    # Grouping by database will allow us to pass the `database_id` to the update
    # function so recreating the dependency tree will be faster.
    for database_id, field_group in itertools.groupby(
        fields, key=lambda f: f.table.database_id
    ):
        fields_in_db = list(field_group)
        database_updated_fields = []
        try:
            with transaction.atomic():
                database_updated_fields = field_type_instance.run_periodic_update(
                    fields_in_db,
                    already_updated_fields=database_updated_fields,
                    skip_search_updates=True,
                    database_id=database_id,
                )
        except Exception:
            tb = traceback.format_exc()
            field_ids = ", ".join(str(field.id) for field in fields_in_db)
            logger.error(
                "Failed to periodically update {field_ids} because of: \n{tb}",
                field_ids=field_ids,
                tb=tb,
            )
        else:
            # Update tsv columns and notify views of the changes.
            SearchHandler.all_fields_values_changed_or_created(database_updated_fields)

            updated_table_ids = list(
                {field.table_id for field in database_updated_fields}
            )
            notify_table_views_updates.delay(updated_table_ids)


@app.task(
    bind=True,
    queue=settings.PERIODIC_FIELD_UPDATE_QUEUE_NAME,
    soft_time_limit=BATCH_UPDATE_SOFT_TIME_LIMIT,
    time_limit=BATCH_UPDATE_HARD_TIME_LIMIT,
)
def update_workspaces_periodic_fields(
    self,
    workspace_ids: list[int],
    update_now: bool = True,
    batch_index: int = 0,
    run_token: Optional[str] = None,
):
    """
    Updates all periodic fields for a batch of workspaces. Extends the per-cycle run
    lock's TTL at the start, but only while this cycle still owns it. If the lock has
    lapsed or a newer cycle took over (e.g. after a long queue delay), the batch stops
    instead of running unprotected and risking an overlap.
    """

    if not SingletonAutoRescheduleFlag(RUN_LOCK_KEY, timeout=RUN_LOCK_TTL).extend_if(
        run_token
    ):
        logger.info(
            "update_workspaces_periodic_fields batch {batch_index} skipped: the run "
            "lock is no longer held by this cycle.",
            batch_index=batch_index,
        )
        return

    for workspace_id in workspace_ids:
        try:
            _update_workspace_periodic_fields(workspace_id, update_now)
        except Exception:
            # Keep going so one failing workspace can't fail the whole batch. A failed
            # batch would skip the chord callback and leave the run lock stranded until
            # its TTL expires.
            logger.exception(
                "Periodic field update failed for workspace {workspace_id}.",
                workspace_id=workspace_id,
            )


@app.task(queue=settings.PERIODIC_FIELD_UPDATE_QUEUE_NAME)
def finish_periodic_fields_update(token: str):
    """Chord callback: release the per-cycle run lock if we still own it."""

    SingletonAutoRescheduleFlag(RUN_LOCK_KEY).clear_if(token)


def _update_workspace_periodic_fields(
    workspace_id: int, update_now: bool = True
) -> None:
    workspace = Workspace.objects.filter(id=workspace_id, trashed=False).first()
    if workspace is None:
        return

    started_at = time.monotonic()
    for field_type_instance in field_type_registry.get_all():
        field_qs = field_type_instance.get_fields_needing_periodic_update()
        if field_qs is None:
            continue
        # Only update this field type if the workspace actually has one due, so we
        # do exactly the same work the old single job did.
        has_due_fields = field_qs.filter(
            table__database__workspace_id=workspace_id,
            table__database__trashed=False,
            table__trashed=False,
        ).exists()
        if not has_due_fields:
            continue
        _run_periodic_field_type_update_per_workspace(
            field_type_instance, workspace, update_now
        )

    elapsed = time.monotonic() - started_at
    if elapsed >= SLOW_WORKSPACE_LOG_THRESHOLD_SECONDS:
        logger.warning(
            "Periodic field update for workspace {workspace_id} took {elapsed:.1f}s.",
            workspace_id=workspace_id,
            elapsed=elapsed,
        )


@app.task(bind=True)
def notify_table_views_updates(self, table_ids):
    """
    Notifies the views of the provided tables that their data has been updated. For
    performance reasons, we fetch all the views with subscriptions in one go and group
    them by table id so we can notify only the views that need to be notified.

    :param table_ids: The ids of the tables that have been updated.
    """

    subquery = ViewSubscription.objects.filter(view_id=OuterRef("id")).values("view_id")
    views_need_notify = (
        View.objects.filter(
            table_id__in=table_ids,
            id=Subquery(subquery),
        )
        .select_related("table")
        .order_by("table_id")
    )

    for _, views_group in itertools.groupby(
        views_need_notify, key=lambda v: v.table_id
    ):
        with transaction.atomic():
            ViewSubscriptionHandler.notify_table_views(
                [view.id for view in views_group]
            )


@app.task(bind=True)
def delete_mentions_marked_for_deletion(self):
    cutoff_time = datetime.now(tz=timezone.utc) - timedelta(
        minutes=settings.STALE_MENTIONS_CLEANUP_INTERVAL_MINUTES
    )
    RichTextFieldMention.objects.filter(
        marked_for_deletion_at__lte=cutoff_time
    ).delete()


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        settings.PERIODIC_FIELD_UPDATE_CRONTAB, run_periodic_fields_updates.s()
    )
    sender.add_periodic_task(
        timedelta(minutes=min(15, settings.STALE_MENTIONS_CLEANUP_INTERVAL_MINUTES)),
        delete_mentions_marked_for_deletion.s(),
    )
