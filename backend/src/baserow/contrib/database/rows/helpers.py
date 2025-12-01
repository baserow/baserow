from typing import Any, Callable, Dict, List, Optional

from django.contrib.auth.models import AbstractUser, AnonymousUser

from opentelemetry import trace

from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.models import RowHistory
from baserow.contrib.database.rows.types import (
    ActionData,
    RelatedRowsDiff,
    RowChangeDiff,
)

tracer = trace.get_tracer(__name__)


def construct_entry_from_action_and_diff(
    user: AbstractUser,
    action: ActionData,
    fields_metadata: Dict[str, Any],
    row_diff: RowChangeDiff,
):
    if isinstance(user, AnonymousUser):
        user.first_name = "Anonymous"
        user.last_name = "User"
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


def extract_row_diff(
    table_id: int,
    row_id: int,
    fields_metadata: Dict[str, Any],
    before_values: Dict[str, Any],
    after_values: Dict[str, Any],
    are_equal: Optional[Callable] = None,
) -> Optional[RowChangeDiff]:
    """
    Extracts the fields that have changed between the before and after values of a
    row. Returns None if no fields have changed.
    """

    if not are_equal:

        def are_equal(field_identifier, after_value, before_value) -> bool:
            field_type = fields_metadata[field_identifier]["type"]
            field_type = field_type_registry.get(field_type)
            return field_type.are_row_values_equal(before_value, after_value)

    changed_fields = {
        k
        for k, v in after_values.items()
        if k != "id" and k in before_values and not are_equal(k, v, before_values[k])
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


def raise_if_ids_mismatch(before_values, after_values, fields_metadata):
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


def update_related_tables_entries(
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

        after_set = set(row_diff.after_values[field_name] or [])
        before_set = set(row_diff.before_values[field_name] or [])

        row_ids_added = after_set - before_set
        _update_linked_row_diff(field_metadata, row_ids_added, "added")

        row_ids_removed = before_set - after_set
        _update_linked_row_diff(field_metadata, row_ids_removed, "removed")
    return related_rows_diff


def construct_related_rows_entries(
    related_rows_diff: RelatedRowsDiff,
    user: AbstractUser,
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
