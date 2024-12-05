import itertools
import traceback
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Type

from django.conf import settings
from django.db import transaction
from django.db.models import Q, QuerySet

from loguru import logger
from opentelemetry import trace

from baserow.config.celery import app
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.periodic_field_update_handler import (
    PeriodicFieldUpdateHandler,
)
from baserow.contrib.database.fields.registries import FieldType, field_type_registry
from baserow.contrib.database.search.handler import SearchHandler
from baserow.contrib.database.table.models import RichTextFieldMention
from baserow.core.models import Workspace
from baserow.core.telemetry.utils import add_baserow_trace_attrs, baserow_trace

tracer = trace.get_tracer(__name__)


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
)
def run_periodic_fields_updates(
    self, workspace_id: Optional[int] = None, update_now: bool = True
):
    """
    Refreshes all the fields that need to be updated periodically for all
    workspaces.
    """

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
            _run_periodic_field_type_update_per_workspace(
                field_type_instance, workspace, update_now
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
            table__trashed=False,
            table__database__trashed=False,
        )
        .select_related("table")
        .order_by("table__database_id")
    )

    all_updated_fields = []
    # Grouping by database will allow us to pass the `database_id` to the update
    # function so recreating the dependency tree will be faster.
    for database_id, field_group in itertools.groupby(
        fields, key=lambda f: f.table.database_id
    ):
        fields_in_db = list(field_group)
        try:
            all_updated_fields = _run_periodic_field_update(
                fields_in_db,
                field_type_instance,
                all_updated_fields,
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

    # After a successful periodic update of all fields, we would need to update the
    # search index for all of them in one function to avoid ending up in a
    # deadlock because rows are updated simultaneously.
    SearchHandler().all_fields_values_changed_or_created(all_updated_fields)


@app.task(bind=True)
def delete_mentions_marked_for_deletion(self):
    cutoff_time = datetime.now(tz=timezone.utc) - timedelta(
        minutes=settings.STALE_MENTIONS_CLEANUP_INTERVAL_MINUTES
    )
    RichTextFieldMention.objects.filter(
        marked_for_deletion_at__lte=cutoff_time
    ).delete()


@baserow_trace(tracer)
def _run_periodic_field_update(
    fields: List[Field],
    field_type_instance: Type[FieldType],
    all_updated_fields: List[Field],
    skip_search_updates: bool = False,
    database_id: Optional[int] = None,
):
    with transaction.atomic():
        return field_type_instance.run_periodic_update(
            fields,
            already_updated_fields=all_updated_fields,
            skip_search_updates=skip_search_updates,
            database_id=database_id,
        )


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        settings.PERIODIC_FIELD_UPDATE_CRONTAB, run_periodic_fields_updates.s()
    )
    sender.add_periodic_task(
        timedelta(minutes=min(15, settings.STALE_MENTIONS_CLEANUP_INTERVAL_MINUTES)),
        delete_mentions_marked_for_deletion.s(),
    )
