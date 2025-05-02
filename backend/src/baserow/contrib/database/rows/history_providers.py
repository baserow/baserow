from collections import defaultdict
from collections.abc import Iterable
from copy import copy
from typing import Any, NamedTuple

from baserow.contrib.database.rows.actions import (  # noqa
    CreateRowActionType,
    CreateRowsActionType,
    DeleteRowActionType,
    DeleteRowsActionType,
    UpdateRowActionType,
    UpdateRowsActionType,
)
from baserow.contrib.database.rows.helpers import (
    construct_entry_from_action_and_diff,
    construct_related_rows_entries,
    extract_row_diff,
    raise_if_ids_mismatch,
    update_related_tables_entries,
)
from baserow.contrib.database.rows.models import RowHistory
from baserow.contrib.database.rows.registries import RowHistoryProviderType
from baserow.contrib.database.rows.types import (
    ActionData,
    RelatedRowsDiff,
    RowChangeDiff,
)
from baserow.core.action.registries import ActionType, action_type_registry
from baserow.core.action.signals import ActionCommandType
from baserow.core.trash.actions import RestoreFromTrashActionType  # noqa

from .types import AnyUser


class RowChangeData(NamedTuple):
    """
    A container for per-row values change data.
    """

    row_id: int
    before: dict[str, Any]
    after: dict[str, Any]
    metadata: dict[str, Any]


def are_equal_on_create(field_identifier, after_value, before_value) -> bool:
    """
    Dummy equal check for created row.

    Some fields require specific types/values to be passed to
    FieldType.are_values_equal().
    At the moment of creation we don't have knowledge what values should be used, but
    that's fine, because all we need is to know if a value inserted is different from
    empty one for a field.
    :param field_identifier:
    :param before_value:
    :param after_value:
    :return:
    """

    # Both field values are empty, but they may be empty in a different way. Initially,
    # we set an empty string for all values, regardless the field type. `after_value`
    # was processed by field type logic and ORM layer, so it can be of a different type,
    # but still an empty value, i.e. `None`.
    if not before_value and not after_value:
        return True
    return before_value == after_value


class BaseActionTypeRowHistoryProvider(RowHistoryProviderType):
    """
    Base class for row values change history provider. This base class provides a
    skeleton of getting rows values diff. A subclass should implement two methods:
    * get_changed_rows - returns iterable with per-row change data
    * get_row_history_entries - returns a list of RowHistory entries for a row
    """

    def get_row_history(self, user: AnyUser, params: ActionData) -> list[RowHistory]:
        """
        Skeleton method to generate row history entries for an action.
        """

        action_type: ActionType = params.type
        action = action_type_registry.get(action_type)
        command_type = params.command_type
        action_params = action.serialized_to_params(params.params)

        row_history_entries = []
        related_rows_diff: RelatedRowsDiff = defaultdict(
            lambda: defaultdict(lambda: defaultdict(dict))
        )
        for row_change in self.get_changed_rows(command_type, action_params):
            row_history_items = self.get_row_history_entries(
                user,
                command_type,
                params,
                action_params,
                row_change,
                related_rows_diff,
            )
            row_history_entries.extend(row_history_items)

        related_rows = self.get_related_rows_history(related_rows_diff, user, params)
        row_history_entries.extend(related_rows)
        return row_history_entries

    def get_related_rows_history(
        self,
        related_rows_diff: RelatedRowsDiff,
        user: AnyUser,
        params: ActionData,
    ):
        related_entries = construct_related_rows_entries(
            related_rows_diff, user, params
        )
        return related_entries

    def get_changed_rows(
        self, command_type: ActionCommandType, params: ActionType.Params
    ) -> Iterable[RowChangeData]:
        raise NotImplementedError()

    def get_row_history_entries(
        self,
        user: AnyUser,
        command_type: ActionCommandType,
        params: ActionData,
        action_params: ActionType.Params,
        row_change: RowChangeData,
        related_rows_diff: RelatedRowsDiff,
    ) -> list[RowHistory]:
        raise NotImplementedError()


class RestoreFromTrashHistoryProvider(BaseActionTypeRowHistoryProvider):
    type = RestoreFromTrashActionType.type

    def get_changed_rows(
        self, command_type: ActionCommandType, params: RestoreFromTrashActionType.Params
    ) -> Iterable[RowChangeData]:
        if params.item_type != "row":
            return []

        return [RowChangeData(row_id=params.item_id, before={}, after={}, metadata={})]

    def get_row_history_entries(
        self,
        user: AnyUser,
        command_type: ActionCommandType,
        params: ActionData,
        action_params: RestoreFromTrashActionType.Params,
        row_change: RowChangeData,
        related_rows_diff: RelatedRowsDiff,
    ) -> list[RowHistory]:
        table_id = action_params.parent_item_id
        row_id = row_change.row_id
        row_diff = RowChangeDiff(
            table_id=table_id,
            row_id=row_id,
            changed_field_names=[],
            before_values={},
            after_values={},
        )

        entry = construct_entry_from_action_and_diff(
            user,
            params,
            {},
            row_diff,
        )
        return [entry]


class CreateRowHistoryMixin:
    def get_related_rows_history(
        self,
        related_rows_diff,
        user: AnyUser,
        params: ActionData,
    ) -> list:
        return []

    def get_row_history_entries(
        self,
        user: AnyUser,
        command_type: ActionCommandType,
        params: ActionData,
        action_params: CreateRowsActionType.Params,
        row_change: RowChangeData,
        related_rows_diff: RelatedRowsDiff,
    ) -> list[RowHistory]:
        row_history_entries = []
        table_id = action_params.table_id
        row_id, before, after, metadata = row_change

        row_diff = RowChangeDiff(
            table_id=table_id,
            row_id=row_id,
            changed_field_names=[],
            before_values={},
            after_values={},
        )

        # we want full fields value-level diff for DO command only. If we undo/redo
        # we just mark the operation in the history.
        if command_type == ActionCommandType.DO:
            row_diff = (
                extract_row_diff(
                    table_id,
                    row_id,
                    metadata,
                    before,
                    after,
                    are_equal=are_equal_on_create,
                )
                or row_diff
            )
        changed_fields_metadata = {
            k: v for k, v in metadata.items() if k in row_diff.changed_field_names
        }

        entry = construct_entry_from_action_and_diff(
            user,
            params,
            changed_fields_metadata,
            row_diff,
        )
        row_history_entries.append(entry)

        related_row_diff = row_diff
        related_metadata = changed_fields_metadata
        related_field_names = row_diff.changed_field_names

        # Since RowDiffChange is a source of relations information and we've created
        # a full diff for DO, we need to make a full diff for UNDO/REDO for relations.
        if command_type != ActionCommandType.DO:
            related_field_names = [k for k in metadata.keys() if k != "id"]
            related_row_diff = RowChangeDiff(
                table_id=table_id,
                row_id=row_id,
                changed_field_names=related_field_names,
                before_values=before,
                after_values=after,
            )

            related_metadata = {k: v for k, v in metadata.items() if k != "id"}
        update_related_tables_entries(
            related_rows_diff, related_metadata, related_row_diff
        )

        related_action = copy(params)
        # Note: this is an update on a related table
        related_action.type = UpdateRowsActionType.type
        related_entries = construct_related_rows_entries(
            related_rows_diff, user, related_action
        )
        row_history_entries.extend(related_entries)
        return row_history_entries


class CreateRowHistoryProvider(CreateRowHistoryMixin, BaseActionTypeRowHistoryProvider):
    type = CreateRowActionType.type

    def get_changed_rows(
        self,
        command_type: ActionCommandType,
        params: CreateRowActionType.Params,
    ) -> Iterable[RowChangeData]:
        after = params.row_values
        metadata = params.fields_metadata

        before = {"id": params.row_id, **{k: None for k in metadata.keys()}}
        if command_type == ActionCommandType.UNDO:
            before, after = after, before

        yield RowChangeData(
            row_id=params.row_id, before=before, after=after, metadata=metadata
        )


class CreateRowsHistoryProvider(
    CreateRowHistoryMixin, BaseActionTypeRowHistoryProvider
):
    type = CreateRowsActionType.type

    def get_changed_rows(
        self, command_type: ActionCommandType, params: CreateRowsActionType.Params
    ) -> Iterable[RowChangeData]:
        after_values = params.rows_values
        row_ids = params.row_ids
        swap_before_after = command_type == ActionCommandType.UNDO

        for idx, row_id in enumerate(row_ids):
            after = after_values[idx]
            metadata = params.fields_metadata[str(row_id)]
            before = {"id": row_id, **{k: None for k in metadata.keys()}}
            yield RowChangeData(
                row_id=row_id,
                before=before if not swap_before_after else after,
                after=after if not swap_before_after else before,
                metadata=metadata,
            )


class DeleteRowHistoryMixin:
    def get_related_rows_history(
        self,
        related_rows_diff,
        user: AnyUser,
        params: ActionData,
    ) -> list:
        return []

    def get_row_history_entries(
        self,
        user: AnyUser,
        command_type: ActionCommandType,
        params: ActionData,
        action_params: CreateRowsActionType.Params,
        row_change: RowChangeData,
        related_rows_diff: RelatedRowsDiff,
    ) -> list[RowHistory]:
        table_id = action_params.table_id

        row_history_entries = []
        row_id, before, after, metadata = row_change

        row_diff = RowChangeDiff(
            table_id=table_id,
            row_id=row_id,
            changed_field_names=[],
            before_values={},
            after_values={},
        )

        changed_fields_metadata = {}

        entry = construct_entry_from_action_and_diff(
            user,
            params,
            changed_fields_metadata,
            row_diff,
        )
        row_history_entries.append(entry)

        related_row_diff = row_diff
        related_metadata = changed_fields_metadata
        related_field_names = row_diff.changed_field_names

        if command_type != ActionCommandType.DO:
            related_field_names = [k for k in metadata.keys() if k != "id"]
            related_row_diff = RowChangeDiff(
                table_id=table_id,
                row_id=row_id,
                changed_field_names=related_field_names,
                before_values=before,
                after_values=after,
            )

            related_metadata = {k: v for k, v in metadata.items() if k != "id"}
        update_related_tables_entries(
            related_rows_diff, related_metadata, related_row_diff
        )
        related_action = copy(params)
        related_action.type = UpdateRowsActionType.type
        related_entries = construct_related_rows_entries(
            related_rows_diff, user, related_action
        )
        row_history_entries.extend(related_entries)
        return row_history_entries


class DeleteRowHistoryProvider(DeleteRowHistoryMixin, BaseActionTypeRowHistoryProvider):
    type = DeleteRowActionType.type

    def get_changed_rows(
        self, command_type: ActionCommandType, params: DeleteRowActionType.Params
    ) -> Iterable[RowChangeData]:
        row_id = params.row_id
        metadata = {k: v for k, v in params.fields_metadata.items() if k != "id"}
        before = params.values
        after = {"id": row_id, **{k: None for k in metadata.keys()}}
        swap_before_after = command_type == ActionCommandType.UNDO

        yield RowChangeData(
            row_id=row_id,
            before=before if not swap_before_after else after,
            after=after if not swap_before_after else before,
            metadata=metadata,
        )


class DeleteRowsHistoryProvider(
    DeleteRowHistoryMixin, BaseActionTypeRowHistoryProvider
):
    type = DeleteRowsActionType.type

    def get_changed_rows(
        self, command_type: ActionCommandType, params: DeleteRowsActionType.Params
    ) -> Iterable[RowChangeData]:
        swap_before_after = command_type == ActionCommandType.UNDO
        for ridx, row_id in enumerate(params.row_ids):
            before = params.rows_values[ridx]
            metadata = params.fields_metadata[str(row_id)]
            after = {"id": row_id, **{k: None for k in metadata.keys()}}
            yield RowChangeData(
                row_id=row_id,
                before=before if not swap_before_after else after,
                after=after if not swap_before_after else before,
                metadata=metadata,
            )


class UpdateRowsHistoryProvider(BaseActionTypeRowHistoryProvider):
    type = UpdateRowsActionType.type

    def get_changed_rows(
        self, command_type: ActionCommandType, params: UpdateRowsActionType.Params
    ) -> Iterable[RowChangeData]:
        after_values = params.row_values

        swap_before_after = command_type == ActionCommandType.UNDO

        for idx, row_id in enumerate(params.row_ids):
            after = after_values[idx]
            before = params.original_rows_values_by_id[row_id]
            metadata = params.updated_fields_metadata_by_row_id[row_id]
            yield RowChangeData(
                row_id=row_id,
                before=before if not swap_before_after else after,
                after=after if not swap_before_after else before,
                metadata=metadata,
            )

    def get_row_history_entries(
        self,
        user: AnyUser,
        command_type: ActionCommandType,
        params: ActionData,
        action_params: UpdateRowsActionType.Params,
        row_change: RowChangeData,
        related_rows_diff: RelatedRowsDiff,
    ) -> list[RowHistory]:
        row_history_entries = []
        table_id = action_params.table_id
        row_id, before, after, fields_metadata = row_change

        raise_if_ids_mismatch(before, after, fields_metadata)
        row_diff = extract_row_diff(table_id, row_id, fields_metadata, before, after)
        if row_diff is not None:
            changed_fields_metadata = {
                k: v
                for k, v in fields_metadata.items()
                if k in row_diff.changed_field_names
            }

            entry = construct_entry_from_action_and_diff(
                user,
                params,
                changed_fields_metadata,
                row_diff,
            )
            row_history_entries.append(entry)
            update_related_tables_entries(
                related_rows_diff, changed_fields_metadata, row_diff
            )

        return row_history_entries
