import itertools
import time
import traceback
from datetime import datetime, timedelta, timezone
from typing import Optional, Type
from uuid import uuid4

from django.conf import settings
from django.db import OperationalError, connection, transaction
from django.db.models import OuterRef, Q, QuerySet, Subquery

from celery import chord, group
from celery.exceptions import SoftTimeLimitExceeded
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
from baserow.core.psycopg import is_query_canceled_error, tighten_statement_timeout
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

# A batch stops this many seconds before its soft limit. The soft limit can't interrupt
# a running SQL statement, so statements get a Postgres statement_timeout that ends
# them by this deadline instead.
BATCH_UPDATE_DEADLINE_MARGIN_SECONDS = 10

# Django runs these to end a nested atomic block. They must run even after the
# deadline or a failed query, or the transaction can't be cleaned up.
_SAVEPOINT_SQL_PREFIXES = ("SAVEPOINT", "RELEASE SAVEPOINT", "ROLLBACK TO SAVEPOINT")


class PeriodicFieldUpdateTimeBudgetExceeded(SoftTimeLimitExceeded):
    """
    The batch ran out of time before this update could finish. It subclasses the soft
    limit exception so it's handled the same way everywhere.
    """


def _ensure_time_left(deadline: float) -> int:
    """
    Returns the milliseconds left until the deadline. Raises if less than a second is
    left.
    """

    time_left_ms = int((deadline - time.monotonic()) * 1000)
    if time_left_ms < 1000:
        raise PeriodicFieldUpdateTimeBudgetExceeded()
    return time_left_ms


def _statement_deadline(deadline: float):
    """
    A `connection.execute_wrapper` that stops each query in a transaction from
    running past the deadline. Postgres applies statement_timeout per statement, so it
    is lowered again before every query. Queries outside a transaction are left alone:
    they can't get a local timeout, and they include on_commit hooks for data that is
    already committed.
    """

    def wrapper(execute, sql, params, many, context):
        db = context["connection"]
        if (
            not db.in_atomic_block
            or db.needs_rollback
            or (isinstance(sql, str) and sql.startswith(_SAVEPOINT_SQL_PREFIXES))
        ):
            return execute(sql, params, many, context)

        time_left_ms = _ensure_time_left(deadline)
        # A separate cursor skips this wrapper, and works when the query uses a named
        # cursor, which can only execute once.
        with db.wrap_database_errors, db.connection.cursor() as cursor:
            tighten_statement_timeout(cursor, time_left_ms)
        try:
            return execute(sql, params, many, context)
        except OperationalError as exc:
            if is_query_canceled_error(exc) and deadline - time.monotonic() < 1:
                raise PeriodicFieldUpdateTimeBudgetExceeded() from exc
            raise

    return wrapper


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
    the whole instance at once. Raising the count spreads the work across more workers.
    When ``dispatch`` is False the updates run inline instead of being queued, which the
    management command uses to run synchronously. The inline path bypasses the run lock,
    so it can overlap with an in-flight beat cycle.
    """

    if not dispatch:
        for wid in _collect_ordered_workspace_ids(workspace_id):
            _update_workspace_periodic_fields(wid, update_now)
        return

    # One cycle at a time. Acquire the fenced run lock before the (potentially heavy)
    # eligibility scan, so an overlapping run skips cheaply instead of scanning and
    # discarding the result. Overlaps are likeliest on large instances, where the scan
    # is heaviest.
    token = self.request.id or uuid4().hex
    flag = SingletonAutoRescheduleFlag(RUN_LOCK_KEY, timeout=RUN_LOCK_TTL)
    if not flag.acquire(token):
        # Log as an error so self-hosters can see and act on it: a cycle is still
        # running when the next one starts, so this run is skipped and periodic fields
        # refresh less often than configured. The two settings below are the levers to
        # fix it, so name them explicitly.
        logger.error(
            "run_periodic_fields_updates skipped: the previous cycle is still running, "
            "so periodic fields will refresh less often than expected. Give each cycle "
            "more time by increasing the interval between runs "
            "(BASEROW_PERIODIC_FIELD_UPDATE_CRONTAB), or make each cycle finish faster "
            "by spreading the work across more tasks "
            "(BASEROW_PERIODIC_FIELD_UPDATE_BATCH_COUNT)."
        )
        return

    try:
        ordered_ids = _collect_ordered_workspace_ids(workspace_id)
        if not ordered_ids:
            # Nothing to do this cycle: release the lock we just took.
            flag.clear_if(token)
            return

        batch_count = max(1, settings.PERIODIC_FIELD_UPDATE_BATCH_COUNT)
        # Round-robin the ordered ids across batches (0, n, 2n… then 1, n+1…) so every
        # batch stays oldest-first and the most overdue workspaces are picked up first in
        # parallel, instead of being stranded at the tail of a single batch.
        batches = [ordered_ids[i::batch_count] for i in range(batch_count)]
        batches = [batch for batch in batches if batch]
        header = group(
            update_workspaces_periodic_fields.s(
                batch_ids,
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


def _collect_ordered_workspace_ids(workspace_id: Optional[int] = None) -> list[int]:
    """
    Ids of the workspaces with a periodic field due, most out-of-date (oldest ``now``)
    first, like the old job did, so a backlog still clears the most overdue ones first.
    """

    workspace_ids = _collect_workspace_ids_needing_update(workspace_id)
    return list(
        Workspace.objects.filter(id__in=workspace_ids)
        .order_by("now")
        .values_list("id", flat=True)
    )


@baserow_trace(tracer)
def _run_periodic_field_type_update_per_workspace(
    field_type_instance: Type[FieldType], workspace: Workspace, update_now: bool = True
):
    qs = field_type_instance.get_fields_needing_periodic_update()
    if qs is None:
        return

    # In a transaction so the batch deadline's statement_timeout covers these too.
    with transaction.atomic():
        fields = list(
            qs.filter(
                table__database__workspace_id=workspace.id,
                table__database__trashed=False,
                table__trashed=False,
            )
            .select_related("table__database")
            .order_by("table__database_id")
        )
        # Nothing due for this field type: skip before refreshing `now` so an idle
        # workspace isn't touched (and this is the only place we filter the fields).
        if not fields:
            return

        if update_now:
            workspace.refresh_now()
    add_baserow_trace_attrs(update_now=update_now, workspace_id=workspace.id)

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
                # Schedules the tsv update on commit. Called inside the transaction so
                # the table lookups it needs are covered by the batch deadline.
                SearchHandler.all_fields_values_changed_or_created(
                    database_updated_fields
                )
        except SoftTimeLimitExceeded:
            # Let it propagate so the batch stops cleanly instead of being swallowed
            # and running until the hard limit SIGKILLs the task.
            raise
        except Exception:
            tb = traceback.format_exc()
            field_ids = ", ".join(str(field.id) for field in fields_in_db)
            logger.error(
                "Failed to periodically update {field_ids} because of: \n{tb}",
                field_ids=field_ids,
                tb=tb,
            )
        else:
            # Notify views of the changes.
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
    lock's TTL before each workspace, but only while this cycle still owns it. If the
    lock has lapsed or a newer cycle took over (e.g. after a long queue delay), the batch
    stops instead of running unprotected and risking an overlap. Heartbeating per
    workspace (rather than once at the start) keeps the TTL fresh through a long batch, so
    the next serialized batch still finds the lock held when it dequeues.
    """

    deadline = (
        time.monotonic()
        + BATCH_UPDATE_SOFT_TIME_LIMIT
        - BATCH_UPDATE_DEADLINE_MARGIN_SECONDS
    )
    flag = SingletonAutoRescheduleFlag(RUN_LOCK_KEY, timeout=RUN_LOCK_TTL)
    with connection.execute_wrapper(_statement_deadline(deadline)):
        for index, workspace_id in enumerate(workspace_ids):
            if not flag.extend_if(run_token):
                # Warn (not info): this drops the rest of the batch's work for the
                # cycle, so operators should see it. A newer cycle owns the lock or it
                # expired.
                logger.warning(
                    "update_workspaces_periodic_fields batch {batch_index} stopped: the "
                    "run lock is no longer held by this cycle, so its remaining "
                    "{skipped} workspace(s) are skipped this cycle.",
                    batch_index=batch_index,
                    skipped=len(workspace_ids) - index,
                )
                return
            try:
                # Checked before starting, so a workspace that can't be processed keeps
                # its `now` and is first in line next cycle.
                _ensure_time_left(deadline)
                _update_workspace_periodic_fields(workspace_id, update_now)
            except SoftTimeLimitExceeded:
                # Out of time: stop cleanly so the task succeeds and the chord callback
                # releases the lock. Continuing would run until the hard limit SIGKILLs
                # the batch, stranding the lock until its TTL. The unprocessed
                # workspaces keep their stale `now` and are picked up next cycle.
                logger.warning(
                    "update_workspaces_periodic_fields batch {batch_index} ran out of "
                    "time at workspace {workspace_id}; stopping so the lock is "
                    "released. {skipped} workspace(s) are skipped this cycle.",
                    batch_index=batch_index,
                    workspace_id=workspace_id,
                    skipped=len(workspace_ids) - index,
                )
                return
            except Exception:
                # Keep going so one failing workspace can't fail the whole batch. A
                # failed batch would skip the chord callback and leave the run lock
                # stranded until its TTL expires.
                logger.exception(
                    "Periodic field update failed for workspace {workspace_id}.",
                    workspace_id=workspace_id,
                )


@app.task(queue=settings.PERIODIC_FIELD_UPDATE_QUEUE_NAME)
def finish_periodic_fields_update(token: str):
    """Chord callback: release the per-cycle run lock if we still own it."""

    SingletonAutoRescheduleFlag(RUN_LOCK_KEY, timeout=RUN_LOCK_TTL).clear_if(token)


def _update_workspace_periodic_fields(
    workspace_id: int, update_now: bool = True
) -> None:
    # In a transaction so the batch deadline's statement_timeout covers it.
    with transaction.atomic():
        workspace = Workspace.objects.filter(id=workspace_id, trashed=False).first()
    if workspace is None:
        return

    started_at = time.monotonic()
    for field_type_instance in field_type_registry.get_all():
        # Each call filters the due fields once and early-returns (before refreshing
        # `now`) when the workspace has none, so idle field types are a no-op.
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
