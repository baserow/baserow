from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from itertools import groupby
from typing import Any, Dict, List, NamedTuple, NewType, Optional

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.db.models import QuerySet
from django.dispatch import receiver

from opentelemetry import trace

from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.actions import UpdateRowsActionType
from baserow.contrib.database.rows.models import RowHistory
from baserow.contrib.database.rows.registries import change_row_history_registry
from baserow.contrib.database.rows.signals import rows_history_updated
from baserow.core.action.signals import ActionCommandType, action_done
from baserow.core.models import Workspace
from baserow.core.telemetry.utils import baserow_trace

tracer = trace.get_tracer(__name__)

FieldName = NewType("FieldName", str)

# Dict of table_id -> row_id -> field_name ->
# {added: List[row_id], removed:List[row_id], metadata: Dict}
RelatedRowsDiff = Dict[int, Dict[int, Dict[str, Dict[str, Any]]]]


@dataclass
class ActionData:
    uuid: str
    type: str
    timestamp: datetime
    command_type: ActionCommandType
    params: Dict[str, Any]


class RowChangeDiff(NamedTuple):
    """
    Represents the diff between the before and after values of a row. It
    contains the names of the fields that have changed, as well as the before
    and after values of those fields.
    """

    row_id: int
    table_id: int
    changed_field_names: List[FieldName]
    before_values: Dict[FieldName, Any]
    after_values: Dict[FieldName, Any]


class RowHistoryHandler:
    @classmethod
    def _construct_entry_from_action_and_diff(
        cls,
        user: AbstractBaseUser,
        action: ActionData,
        fields_metadata: Dict[str, Any],
        row_diff: RowChangeDiff,
    ):
        return RowHistory(
            user_id=user.id,
            user_name=user.first_name,
            table_id=row_diff.table_id,
            row_id=row_diff.row_id,
            field_names=row_diff.changed_field_names,
            fields_metadata=fields_metadata,
            action_uuid=action.uuid,
            action_command_type=action.command_type.value,
            action_timestamp=action.timestamp,
            action_type=action.type,
            before_values=row_diff.before_values,
            after_values=row_diff.after_values,
        )

    @classmethod
    def _extract_row_diff(
        cls,
        table_id: int,
        row_id: int,
        fields_metadata: Dict[str, Any],
        before_values: Dict[str, Any],
        after_values: Dict[str, Any],
    ) -> Optional[RowChangeDiff]:
        """
        Extracts the fields that have changed between the before and after values of a
        row. Returns None if no fields have changed.
        """

        def are_equal(field_identifier, before_value, after_value) -> bool:
            field_type = fields_metadata[field_identifier]["type"]
            field_type = field_type_registry.get(field_type)
            return field_type.are_row_values_equal(before_value, after_value)

        changed_fields = {
            k
            for k, v in after_values.items()
            if k != "id"
            and k in before_values
            and not are_equal(k, v, before_values[k])
        }
        if not changed_fields:
            return None

        before_fields = {
            k: field_type_registry.get(
                fields_metadata[k]["type"]
            ).prepare_value_for_row_history(v)
            for k, v in before_values.items()
            if k in changed_fields
        }
        after_fields = {
            k: field_type_registry.get(
                fields_metadata[k]["type"]
            ).prepare_value_for_row_history(v)
            for k, v in after_values.items()
            if k in changed_fields
        }
        return RowChangeDiff(
            row_id, table_id, list(changed_fields), before_fields, after_fields
        )

    @classmethod
    def _raise_if_ids_mismatch(cls, before_values, after_values, fields_metadata):
        if (
            before_values["id"] != after_values["id"]
            or before_values["id"] != fields_metadata["id"]
        ):
            raise ValueError(
                f"Row ID mismatch between before values, after values and metadata. It should be: "
                f"{before_values['id']} == {after_values['id']} == {fields_metadata['id']}. "
                "Please ensure that the order of the rows in before, after and fields metadata "
                "are the same. This should never happen."
            )

    @classmethod
    def _update_related_tables_entries(
        cls,
        related_rows_diff: RelatedRowsDiff,
        fields_metadata: Dict[str, Any],
        row_diff: RowChangeDiff,
    ) -> RelatedRowsDiff:
        """
        Updates the record of changes in related tables when link_row fields are
        modified.

        When a row's link_row field is updated (adding or removing connections to rows
        in another table), this method tracks those changes from the perspective of the
        rows in the related table, so that history can be properly displayed for both
        sides of the relationship.

        The method updates related_rows_diff in-place, maintaining a record of which
        rows were added or removed from each link relationship.

        :param related_rows_diff: Nested dictionary tracking changes for each affected
            related row
        :param fields_metadata: Metadata about the fields that were changed in
            this update
        :param row_diff: The changes made to the current row, including before/after
            values
        :return: The updated related_rows_diff dictionary
        """

        def _init_linked_row_diff(linked_field_id):
            return {
                "added": [],
                "removed": [],
                "metadata": {
                    "id": linked_field_id,
                    "type": "link_row",
                    "linked_rows": {},
                },
            }

        def _update_linked_row_diff(
            field_metadata: Dict[str, Any], row_ids_set: set[int], key: str
        ):
            linked_table_id = field_metadata["linked_table_id"]
            linked_field_id = field_metadata["linked_field_id"]
            linked_field_name = f"field_{linked_field_id}"

            for linked_row_id in row_ids_set:
                linked_diff = related_rows_diff[linked_table_id][linked_row_id][
                    linked_field_name
                ]
                if not linked_diff:
                    linked_diff = _init_linked_row_diff(linked_field_id)
                    related_rows_diff[linked_table_id][linked_row_id][
                        linked_field_name
                    ] = linked_diff
                linked_diff[key].append(row_id)
                linked_diff["metadata"]["linked_rows"][row_id] = {
                    "value": field_metadata["primary_value"]
                }

        row_id = row_diff.row_id
        for field_name in row_diff.changed_field_names:
            field_metadata = fields_metadata[field_name]

            # Ignore fields that are not link_row fields or that doesn't have a related
            # field in the linked table.
            if (
                field_metadata["type"] != "link_row"
                or not field_metadata["linked_field_id"]
            ):
                continue

            after_set = set(row_diff.after_values[field_name])
            before_set = set(row_diff.before_values[field_name])

            row_ids_added = after_set - before_set
            _update_linked_row_diff(field_metadata, row_ids_added, "added")

            row_ids_removed = before_set - after_set
            _update_linked_row_diff(field_metadata, row_ids_removed, "removed")

        return related_rows_diff

    @classmethod
    def _construct_related_rows_entries(
        cls,
        related_rows_diff: RelatedRowsDiff,
        user: AbstractBaseUser,
        action: ActionData,
    ) -> List[RowHistory]:
        """
        Creates RowHistory entries for rows in related tables that were affected by
        changes to the current row. Specifically, when a link_row field is updated,
        this method ensures that the changes are also tracked from the perspective of
        the related rows.

        :param related_rows_diff: A nested dictionary that tracks changes for each
            affected related row. It includes details about rows added or removed
            from link_row relationships.
        :param user: The user who performed the action that triggered the changes.
        :param action: The action metadata that describes the operation performed.
        :return: A list of RowHistory entries representing the changes for the
            related rows.
        """

        entries = []
        for linked_table_id, table_changes in related_rows_diff.items():
            for linked_row_id, row_changes in table_changes.items():
                field_names = list(row_changes.keys())
                fields_metadata, before_values, after_values = {}, {}, {}

                for field_name in field_names:
                    row_field_changes = row_changes[field_name]
                    fields_metadata[field_name] = row_field_changes["metadata"]
                    before_values[field_name] = row_field_changes["removed"]
                    after_values[field_name] = row_field_changes["added"]

                linked_entry = RowHistory(
                    user_id=user.id,
                    user_name=user.first_name,
                    table_id=linked_table_id,
                    row_id=linked_row_id,
                    field_names=field_names,
                    fields_metadata=fields_metadata,
                    action_uuid=action.uuid,
                    action_command_type=action.command_type.value,
                    action_timestamp=action.timestamp,
                    action_type=action.type,
                    before_values=before_values,
                    after_values=after_values,
                )
                entries.append(linked_entry)
        return entries

    @classmethod
    @baserow_trace(tracer)
    def record_history_from_update_rows_action(
        cls,
        user: AbstractBaseUser,
        action: ActionData,
    ):
        params = UpdateRowsActionType.serialized_to_params(action.params)
        table_id = params.table_id
        after_values = params.row_values
        before_values = [
            params.original_rows_values_by_id[r["id"]] for r in after_values
        ]

        if action.command_type == ActionCommandType.UNDO:
            before_values, after_values = after_values, before_values

        row_history_entries = []
        related_rows_diff: RelatedRowsDiff = defaultdict(
            lambda: defaultdict(lambda: defaultdict(dict))
        )
        for i, after in enumerate(after_values):
            before = before_values[i]
            fields_metadata = params.updated_fields_metadata_by_row_id[after["id"]]
            cls._raise_if_ids_mismatch(before, after, fields_metadata)

            row_id = after["id"]
            row_diff = cls._extract_row_diff(
                table_id, row_id, fields_metadata, before, after
            )
            if row_diff is None:
                continue

            changed_fields_metadata = {
                k: v
                for k, v in fields_metadata.items()
                if k in row_diff.changed_field_names
            }

            entry = cls._construct_entry_from_action_and_diff(
                user,
                action,
                changed_fields_metadata,
                row_diff,
            )
            row_history_entries.append(entry)
            cls._update_related_tables_entries(
                related_rows_diff, changed_fields_metadata, row_diff
            )

        related_entries = cls._construct_related_rows_entries(
            related_rows_diff, user, action
        )
        row_history_entries.extend(related_entries)

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
        delete_qs._raw_delete(delete_qs.db)


ROW_HISTORY_ACTIONS = {
    UpdateRowsActionType.type: RowHistoryHandler.record_history_from_update_rows_action,
}


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

    if action_type and action_type.type in ROW_HISTORY_ACTIONS:
        add_entry_handler = ROW_HISTORY_ACTIONS[action_type.type]
        add_entry_handler(
            user,
            ActionData(
                action_uuid,
                action_type.type,
                action_timestamp,
                action_command_type,
                action_params,
            ),
        )
