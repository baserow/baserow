from typing import Any, NamedTuple
from unittest.mock import MagicMock

from django.contrib.auth.models import AbstractUser

import pytest
from pydantic import ValidationError

from baserow.contrib.database.fields.actions import UpdateFieldActionType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field, SelectOption
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.models import Table
from baserow.core.action.handler import ActionHandler
from baserow_enterprise.assistant.tools.database.tools import (
    delete_fields,
    get_tables_schema,
    update_fields,
)
from baserow_enterprise.assistant.tools.database.types import (
    FieldItemUpdate,
    SelectOptionCreate,
    SelectOptionUpdate,
)

from .utils import make_test_ctx

SESSION_ID = "session-id"


class StatusField(NamedTuple):
    user: AbstractUser
    ctx: MagicMock
    table: Table
    field: Field
    field_type: str
    open: SelectOption
    closed: SelectOption
    row_id: int
    cell: list[int]


def _create_status_field(data_fixture: Any, field_type: str) -> StatusField:
    """
    Create a Status field whose default is Open (light-red), plus Closed (blue) and
    one row using Closed, or both options for a multiple select.
    """

    user = data_fixture.create_user(session_id=SESSION_ID)
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    field = getattr(data_fixture, f"create_{field_type}_field")(
        table=table, name="Status"
    )
    open_option = data_fixture.create_select_option(
        field=field, value="Open", color="light-red", order=0
    )
    closed_option = data_fixture.create_select_option(
        field=field, value="Closed", color="blue", order=1
    )
    if field_type == "multiple_select":
        field.multiple_select_default = [open_option.id]
        cell = sorted([open_option.id, closed_option.id])
        value = cell
    else:
        field.single_select_default = open_option.id
        cell = [closed_option.id]
        value = closed_option.id
    field.save()
    row = RowHandler().create_row(user, table, {field.db_column: value})
    return StatusField(
        user,
        make_test_ctx(user, workspace),
        table,
        field,
        field_type,
        open_option,
        closed_option,
        row.id,
        cell,
    )


def _options(status: StatusField) -> list[tuple[int, str, str]]:
    return [(o.id, o.value, o.color) for o in status.field.select_options.all()]


def _cell(status: StatusField) -> list[int]:
    row = status.table.get_model().objects.get(id=status.row_id)
    value = getattr(row, status.field.db_column)
    if status.field_type == "multiple_select":
        return sorted(option.id for option in value.all())
    return [value.id] if value else []


def _default(status: StatusField) -> list[int]:
    field = FieldHandler().get_field(status.field.id).specific
    if status.field_type == "multiple_select":
        return field.multiple_select_default
    return [field.single_select_default] if field.single_select_default else []


@pytest.mark.django_db
def test_update_field_name(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, name="Old Name")

    ctx = make_test_ctx(user, workspace)
    result = update_fields(
        ctx,
        fields=[FieldItemUpdate(field_id=field.id, name="New Name")],
        thought="rename field",
    )

    assert result["updated_fields"][0]["name"] == "New Name"
    assert result["updated_fields"][0]["id"] == field.id
    assert result["changed"] is True

    # Verify in DB
    refreshed = FieldHandler().get_field(field.id)
    assert refreshed.name == "New Name"


@pytest.mark.django_db
def test_update_number_field_decimal_places(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_number_field(
        table=table, name="Price", number_decimal_places=0
    )

    ctx = make_test_ctx(user, workspace)
    result = update_fields(
        ctx,
        fields=[FieldItemUpdate(field_id=field.id, decimal_places=2)],
        thought="change decimal places",
    )

    assert result["updated_fields"][0]["decimal_places"] == 2


@pytest.mark.django_db
def test_update_select_field_options(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_single_select_field(table=table, name="Status")

    ctx = make_test_ctx(user, workspace)
    result = update_fields(
        ctx,
        fields=[
            FieldItemUpdate(
                field_id=field.id,
                add_options=[
                    SelectOptionCreate(value="Open", color="green"),
                    SelectOptionCreate(value="Closed", color="red"),
                ],
            )
        ],
        thought="add options",
    )

    updated = result["updated_fields"][0]
    assert len(updated["options"]) == 2
    option_values = {o["value"] for o in updated["options"]}
    assert option_values == {"Open", "Closed"}


@pytest.mark.django_db
@pytest.mark.parametrize("field_type", ["single_select", "multiple_select"])
@pytest.mark.parametrize("add_options", [[{"value": "New"}], ["New"]])
def test_update_select_options_adds_without_changing_existing_ones(
    data_fixture, field_type, add_options
):
    status = _create_status_field(data_fixture, field_type)

    result = update_fields(
        status.ctx,
        fields=[
            FieldItemUpdate.model_validate(
                {"field_id": status.field.id, "add_options": add_options}
            )
        ],
        thought="add an option",
    )

    assert "errors" not in result
    stored = _options(status)
    assert stored[:2] == [
        (status.open.id, "Open", "light-red"),
        (status.closed.id, "Closed", "blue"),
    ]
    assert stored[2][1:] == ("New", "green")
    assert _cell(status) == status.cell
    assert _default(status) == [status.open.id]


@pytest.mark.django_db
@pytest.mark.parametrize("field_type", ["single_select", "multiple_select"])
@pytest.mark.parametrize("value", ["Open", "closed "])
def test_update_select_options_rejects_adding_a_value_that_exists(
    data_fixture, field_type, value
):
    status = _create_status_field(data_fixture, field_type)

    result = update_fields(
        status.ctx,
        fields=[
            FieldItemUpdate.model_validate(
                {"field_id": status.field.id, "add_options": [value, "New"]}
            )
        ],
        thought="add options",
    )

    (error,) = result["errors"]
    existing = status.open if value == "Open" else status.closed
    assert f"'{value}' (option {existing.id})" in error
    assert "update_options" in error
    assert _options(status) == [
        (status.open.id, "Open", "light-red"),
        (status.closed.id, "Closed", "blue"),
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("field_type", ["single_select", "multiple_select"])
def test_update_select_options_renames_and_recolors_by_id(data_fixture, field_type):
    status = _create_status_field(data_fixture, field_type)

    result = update_fields(
        status.ctx,
        fields=[
            FieldItemUpdate(
                field_id=status.field.id,
                update_options=[
                    SelectOptionUpdate(id=status.open.id, value="To do"),
                    SelectOptionUpdate(id=status.closed.id, color="green"),
                ],
            )
        ],
        thought="rename and recolor",
    )

    assert "errors" not in result
    assert _options(status) == [
        (status.open.id, "To do", "light-red"),
        (status.closed.id, "Closed", "green"),
    ]
    assert _cell(status) == status.cell
    assert _default(status) == [status.open.id]


def test_update_select_options_need_a_value_or_color():
    with pytest.raises(ValidationError, match="needs a new value or color"):
        SelectOptionUpdate(id=1)


@pytest.mark.django_db
def test_update_select_options_adds_a_value_freed_by_a_rename(data_fixture):
    status = _create_status_field(data_fixture, "single_select")

    result = update_fields(
        status.ctx,
        fields=[
            FieldItemUpdate.model_validate(
                {
                    "field_id": status.field.id,
                    "update_options": [{"id": status.open.id, "value": "To do"}],
                    "add_options": ["Open"],
                }
            )
        ],
        thought="rename Open and add a new Open",
    )

    assert "errors" not in result
    stored = _options(status)
    assert stored[:2] == [
        (status.open.id, "To do", "light-red"),
        (status.closed.id, "Closed", "blue"),
    ]
    assert stored[2][1:] == ("Open", "green")
    assert _default(status) == [status.open.id]


@pytest.mark.django_db
@pytest.mark.parametrize("field_type", ["single_select", "multiple_select"])
def test_update_select_options_removes_only_the_listed_options(
    data_fixture, field_type
):
    status = _create_status_field(data_fixture, field_type)

    result = update_fields(
        status.ctx,
        fields=[
            FieldItemUpdate(field_id=status.field.id, remove_options=[status.closed.id])
        ],
        thought="remove an option",
    )

    assert "errors" not in result
    assert _options(status) == [(status.open.id, "Open", "light-red")]
    expected_cell = [status.open.id] if field_type == "multiple_select" else []
    assert _cell(status) == expected_cell
    assert _default(status) == [status.open.id]


@pytest.mark.django_db
@pytest.mark.parametrize("field_type", ["single_select", "multiple_select"])
def test_update_select_options_removing_the_default_option_clears_it_until_undo(
    data_fixture, field_type
):
    status = _create_status_field(data_fixture, field_type)

    result = update_fields(
        status.ctx,
        fields=[
            FieldItemUpdate(field_id=status.field.id, remove_options=[status.open.id])
        ],
        thought="remove the default option",
    )

    assert "errors" not in result
    assert _options(status) == [(status.closed.id, "Closed", "blue")]
    assert _default(status) == []

    ActionHandler.undo(
        status.user, [UpdateFieldActionType.scope(status.table.id)], SESSION_ID
    )

    assert _options(status) == [
        (status.open.id, "Open", "light-red"),
        (status.closed.id, "Closed", "blue"),
    ]
    assert _cell(status) == status.cell
    assert _default(status) == [status.open.id]


@pytest.mark.django_db
@pytest.mark.parametrize("field_type", ["single_select", "multiple_select"])
@pytest.mark.parametrize(
    "case,message",
    [
        ("other_field", "are not options of this field"),
        ("unknown_id", "are not options of this field"),
        ("changed_twice", "are changed more than once"),
        ("changed_and_removed", "cannot be changed and removed"),
    ],
)
def test_update_select_options_rejects_invalid_ids(
    data_fixture, field_type, case, message
):
    status = _create_status_field(data_fixture, field_type)
    other_id = data_fixture.create_select_option().id
    closed = {"id": status.closed.id, "value": "Done"}
    payload = {
        "other_field": {"remove_options": [other_id]},
        "unknown_id": {"update_options": [{"id": other_id, "value": "Done"}]},
        "changed_twice": {"update_options": [closed, closed]},
        "changed_and_removed": {
            "update_options": [closed],
            "remove_options": [status.closed.id],
        },
    }[case]
    update = FieldItemUpdate.model_validate({"field_id": status.field.id, **payload})

    result = update_fields(status.ctx, fields=[update], thought="invalid ids")

    (error,) = result["errors"]
    assert message in error
    assert _options(status) == [
        (status.open.id, "Open", "light-red"),
        (status.closed.id, "Closed", "blue"),
    ]
    assert _cell(status) == status.cell


@pytest.mark.django_db
def test_get_tables_schema_reports_the_stored_option_colors(data_fixture):
    status = _create_status_field(data_fixture, "single_select")
    data_fixture.create_select_option(
        field=status.field, value="Later", color="muted-red", order=2
    )

    schema = get_tables_schema(
        status.ctx, table_ids=[status.table.id], full_schema=True, thought="read"
    )

    (field_schema,) = [
        field
        for field in schema["tables_schema"][0]["fields"]
        if field["id"] == status.field.id
    ]
    assert [option["color"] for option in field_schema["options"]] == [
        "light-red",
        "blue",
        "muted-red",
    ]


@pytest.mark.django_db
def test_update_field_no_changes(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, name="Unchanged")

    ctx = make_test_ctx(user, workspace)
    result = update_fields(
        ctx,
        fields=[FieldItemUpdate(field_id=field.id)],
        thought="no changes",
    )

    assert result["updated_fields"][0]["name"] == "Unchanged"
    assert result["changed"] is False


@pytest.mark.django_db
def test_delete_field(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, name="To Delete")

    ctx = make_test_ctx(user, workspace)
    result = delete_fields(
        ctx,
        field_ids=[field.id],
        thought="delete field",
    )

    assert result["deleted_field_ids"] == [field.id]

    # Field should be trashed
    assert not Field.objects.filter(id=field.id).exists()
    assert Field.objects_and_trash.filter(id=field.id, trashed=True).exists()


@pytest.mark.django_db
def test_delete_primary_field_fails(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(
        table=table, name="Primary", primary=True
    )

    ctx = make_test_ctx(user, workspace)
    result = delete_fields(
        ctx,
        field_ids=[primary_field.id],
        thought="try delete primary",
    )

    assert result["deleted_field_ids"] == []
    assert len(result["errors"]) == 1

    # Primary field should still exist
    refreshed = FieldHandler().get_field(primary_field.id)
    assert refreshed.primary is True
