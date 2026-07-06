import itertools
import time
import traceback
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional, Type

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import OuterRef, Q, QuerySet, Subquery

from loguru import logger
from opentelemetry import metrics, trace

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
meter = metrics.get_meter(__name__)

# Distribution of how long a single workspace takes to update. This is the unit of
# work we intend to fan out, so its shape tells us whether the time limit is blown by
# one heavy workspace or by many adding up. workspace_id is deliberately not a metric
# attribute to keep cardinality bounded; heavy workspaces are named in the logs below.
periodic_field_update_workspace_duration = meter.create_histogram(
    name="baserow.periodic_field_update.workspace.duration",
    description="Seconds spent updating periodic fields for a single workspace",
    unit="s",
)
# Total wall-clock of a whole run, to watch headroom against the hard time limit.
# TODO: unused once Task 2 converts the dispatcher into a fan-out; remove then.
periodic_field_update_run_duration = meter.create_histogram(
    name="baserow.periodic_field_update.run.duration",
    description="Seconds spent in a full run_periodic_fields_updates run",
    unit="s",
)
# Wall-clock the dispatcher spends collecting and enqueuing workspace update tasks.
periodic_field_update_dispatch_duration = meter.create_histogram(
    name="baserow.periodic_field_update.dispatch.duration",
    description="Seconds spent dispatching periodic field update tasks",
    unit="s",
)

# A workspace slower than this is logged by id so it can be investigated.
SLOW_WORKSPACE_LOG_THRESHOLD_SECONDS = 60

# Per-workspace update budget. Now that each workspace is its own task this is no longer
# bounded by the run interval, so a slow workspace can't starve the others.
WORKSPACE_UPDATE_SOFT_TIME_LIMIT = settings.PERIODIC_FIELD_UPDATE_TIMEOUT_MINUTES * 60
WORKSPACE_UPDATE_HARD_TIME_LIMIT = WORKSPACE_UPDATE_SOFT_TIME_LIMIT + 30

WORKSPACE_UPDATE_LOCK_KEY = "periodic_field_update_lock:{workspace_id}"


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
    return queryset.distinct().order_by("now")


@app.task(
    bind=True,
    queue=settings.PERIODIC_FIELD_UPDATE_QUEUE_NAME,
    soft_time_limit=settings.PERIODIC_FIELD_UPDATE_TIMEOUT_MINUTES * 60,
    # Keep the hard limit above this task's soft_time_limit, otherwise a shorter
    # global/default CELERY_TASK_TIME_LIMIT could kill the task before the soft limit
    # fires. The 30s margin stays under the task's run interval to avoid overlapping
    # with the next run.
    time_limit=settings.PERIODIC_FIELD_UPDATE_TIMEOUT_MINUTES * 60 + 30,
)
def run_periodic_fields_updates(
    self, workspace_id: Optional[int] = None, update_now: bool = True
):
    """
    Refreshes all the fields that need to be updated periodically for all
    workspaces.
    """

    started_at = time.monotonic()
    # Accumulate wall-clock time spent per workspace so we can log the run's load
    # shape and decide how to fan the work out. See BASEROW-SAAS-BACKEND-3Z.
    per_workspace_seconds: dict[int, float] = defaultdict(float)

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
        for workspace in workspaces:
            workspace_started_at = time.monotonic()
            _run_periodic_field_type_update_per_workspace(
                field_type_instance, workspace, update_now
            )
            per_workspace_seconds[workspace.id] += (
                time.monotonic() - workspace_started_at
            )

    _record_periodic_fields_updates_load(
        time.monotonic() - started_at, per_workspace_seconds
    )


def _percentile(sorted_values: list[float], q: float) -> float:
    """Nearest-rank percentile of an already-sorted list."""

    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, int(q * len(sorted_values)))
    return sorted_values[index]


def _record_periodic_fields_updates_load(
    total_seconds: float, per_workspace_seconds: dict[int, float]
):
    """
    Emits the run's load shape as metrics (durable, distribution) plus logs (naming
    the heavy workspaces). Histograms give the per-workspace distribution and total
    run duration; a warning names any workspace slow enough to be worth investigating.
    """

    periodic_field_update_run_duration.record(total_seconds)
    for seconds in per_workspace_seconds.values():
        periodic_field_update_workspace_duration.record(seconds)

    workspace_count = len(per_workspace_seconds)
    if workspace_count == 0:
        logger.info(
            "run_periodic_fields_updates finished in {total:.1f}s, "
            "no workspaces needed updating.",
            total=total_seconds,
        )
        return

    durations = sorted(per_workspace_seconds.values())
    logger.info(
        "run_periodic_fields_updates finished in {total:.1f}s across {count} "
        "workspaces (busy={busy:.1f}s, max={max:.1f}s, p50={p50:.1f}s, "
        "p90={p90:.1f}s, p99={p99:.1f}s).",
        total=total_seconds,
        count=workspace_count,
        busy=sum(durations),
        max=durations[-1],
        p50=_percentile(durations, 0.5),
        p90=_percentile(durations, 0.9),
        p99=_percentile(durations, 0.99),
    )

    slow_workspaces = sorted(
        (
            (ws_id, seconds)
            for ws_id, seconds in per_workspace_seconds.items()
            if seconds >= SLOW_WORKSPACE_LOG_THRESHOLD_SECONDS
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    if slow_workspaces:
        logger.warning(
            "run_periodic_fields_updates spent over {threshold}s on {count} "
            "workspace(s) (id, seconds): {slow}.",
            threshold=SLOW_WORKSPACE_LOG_THRESHOLD_SECONDS,
            count=len(slow_workspaces),
            slow=[(ws_id, round(seconds, 1)) for ws_id, seconds in slow_workspaces],
        )


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
    soft_time_limit=WORKSPACE_UPDATE_SOFT_TIME_LIMIT,
    time_limit=WORKSPACE_UPDATE_HARD_TIME_LIMIT,
)
def update_workspace_periodic_fields(self, workspace_id: int, update_now: bool = True):
    """Updates all periodic fields for a single workspace."""

    _update_workspace_periodic_fields(workspace_id, update_now)


def _update_workspace_periodic_fields(workspace_id: int, update_now: bool = True):
    # Skip if another task is already updating this workspace so cycles can't stack and
    # double-process it. The lock expires at the hard time limit so a killed task can't
    # wedge it.
    lock = cache.lock(
        WORKSPACE_UPDATE_LOCK_KEY.format(workspace_id=workspace_id),
        timeout=WORKSPACE_UPDATE_HARD_TIME_LIMIT,
    )
    if not lock.acquire(blocking=False):
        logger.debug(
            "Skipping periodic field update for workspace {workspace_id}: "
            "already running.",
            workspace_id=workspace_id,
        )
        return

    try:
        workspace = Workspace.objects.filter(id=workspace_id, trashed=False).first()
        if workspace is None:
            return

        started_at = time.monotonic()
        for field_type_instance in field_type_registry.get_all():
            field_qs = field_type_instance.get_fields_needing_periodic_update()
            if field_qs is None:
                continue
            # only work if this workspace actually has a due field of this type, so we
            # keep the exact selection the monolithic loop had.
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
        periodic_field_update_workspace_duration.record(elapsed)
        if elapsed >= SLOW_WORKSPACE_LOG_THRESHOLD_SECONDS:
            logger.warning(
                "Periodic field update for workspace {workspace_id} took "
                "{elapsed:.1f}s.",
                workspace_id=workspace_id,
                elapsed=elapsed,
            )
    finally:
        lock.release()


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
