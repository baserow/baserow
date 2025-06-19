from datetime import datetime
from itertools import groupby

from django.conf import settings
from django.db import router
from django.db.models import QuerySet
from django.dispatch import receiver

from opentelemetry import trace

from baserow.contrib.database.rows.models import RowHistory
from baserow.contrib.database.rows.registries import (
    RowHistoryProviderType,
    change_row_history_registry,
    row_history_provider_registry,
)
from baserow.contrib.database.rows.signals import rows_history_updated
from baserow.contrib.database.rows.types import ActionData
from baserow.core.action.signals import action_done
from baserow.core.models import Workspace
from baserow.core.telemetry.utils import baserow_trace
from baserow.core.types import AnyUser

tracer = trace.get_tracer(__name__)


class RowHistoryHandler:
    @classmethod
    @baserow_trace(tracer)
    def record_history_from_rows_action(
        cls,
        user: AnyUser,
        action: ActionData,
        row_history_provider: RowHistoryProviderType,
    ):
        row_history_entries = row_history_provider.get_row_history(user, action)

        if row_history_entries:
            row_history_entries = RowHistory.objects.bulk_create(row_history_entries)
            for table_id, per_table_row_history_entries in groupby(
                row_history_entries, lambda e: e.table_id
            ):
                rows_history_updated.send(
                    RowHistoryHandler,
                    table_id=table_id,
                    row_history_entries=list(per_table_row_history_entries),
                )

    @classmethod
    @baserow_trace(tracer)
    def list_row_history(
        cls, workspace: Workspace, table_id: int, row_id: int
    ) -> QuerySet[RowHistory]:
        """
        Returns queryset of row history entries for the provided
        workspace, table_id and row_id.
        """

        queryset = RowHistory.objects.filter(table_id=table_id, row_id=row_id).order_by(
            "-action_timestamp", "-id"
        )

        for op_type in change_row_history_registry.get_all():
            queryset = op_type.apply_to_list_queryset(
                queryset, workspace, table_id, row_id
            )

        return queryset

    @classmethod
    def delete_entries_older_than(cls, cutoff: datetime):
        """
        Deletes all row history entries that are older than the given cutoff date.

        :param cutoff: The date and time before which all entries will be deleted.
        """

        delete_qs = RowHistory.objects.filter(action_timestamp__lt=cutoff)
        delete_qs._raw_delete(using=router.db_for_write(delete_qs.model))


@receiver(action_done)
def on_action_done_update_row_history(
    sender,
    user,
    action_type,
    action_params,
    action_timestamp,
    action_command_type,
    workspace,
    action_uuid,
    **kwargs,
):
    if settings.BASEROW_ROW_HISTORY_RETENTION_DAYS == 0:
        return

    try:
        row_history_provider = row_history_provider_registry.get(action_type.type)
    except row_history_provider_registry.does_not_exist_exception_class:
        return

    action_data = ActionData(
        action_uuid,
        action_type.type,
        action_timestamp,
        action_command_type,
        action_params,
    )
    RowHistoryHandler.record_history_from_rows_action(
        user, action_data, row_history_provider
    )
