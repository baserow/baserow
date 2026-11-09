import asyncio
from typing import Any, NamedTuple
from unittest.mock import MagicMock

from django.contrib.auth.models import AbstractUser
from django.db import IntegrityError

import pytest
from loguru import logger
from pydantic import ValidationError

from baserow.contrib.database.fields.actions import (
    CreateFieldActionType,
    UpdateFieldActionType,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field, SelectOption
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.tools import fields as shared_fields
from baserow.core.action.handler import ActionHandler
from baserow.core.exceptions import PermissionException
from baserow.core.tools.errors import INTERNAL_ERROR_MESSAGE
from baserow_enterprise.assistant.tools.database import helpers
from baserow_enterprise.assistant.tools.database.tools import (
    create_fields,
    create_tables,
    delete_fields,
    get_tables_schema,
    update_fields,
)
from baserow_enterprise.assistant.tools.database.types import (
    FieldItemCreate,
    FieldItemUpdate,
    SelectOptionCreate,
    SelectOptionUpdate,
    TableItemCreate,
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
    assert (error["item"], error["code"]) == (status.field.id, "invalid_input")
    message = error["message"]
    assert (
        f"option {existing.id} '{existing.value}' and the new option '{value}'"
        in message
    )
    assert "case and surrounding spaces are ignored" in message
    assert "Leave out options that already exist" in error["hint"]
    assert _options(status) == [
        (status.open.id, "Open", "light-red"),
        (status.closed.id, "Closed", "blue"),
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "case", ["added_twice", "renamed_onto_another", "renamed_onto_added"]
)
def test_update_select_options_rejects_values_that_would_repeat(data_fixture, case):
    status = _create_status_field(data_fixture, "single_select")
    payload, message = {
        "added_twice": (
            {"add_options": ["New", "new "]},
            "the new option 'New' and the new option 'new '",
        ),
        "renamed_onto_another": (
            {"update_options": [{"id": status.closed.id, "value": "open"}]},
            f"option {status.open.id} 'Open' and option {status.closed.id} renamed "
            "to 'open'",
        ),
        "renamed_onto_added": (
            {
                "update_options": [{"id": status.open.id, "value": "Doing"}],
                "add_options": ["Doing"],
            },
            f"option {status.open.id} renamed to 'Doing' and the new option 'Doing'",
        ),
    }[case]

    result = update_fields(
        status.ctx,
        fields=[
            FieldItemUpdate.model_validate({"field_id": status.field.id, **payload})
        ],
        thought="repeat a value",
    )

    (error,) = result["errors"]
    assert (error["item"], error["code"]) == (status.field.id, "invalid_input")
    assert message in error["message"]
    assert _options(status) == [
        (status.open.id, "Open", "light-red"),
        (status.closed.id, "Closed", "blue"),
    ]


@pytest.mark.django_db
def test_update_select_options_leaves_existing_duplicates_alone(data_fixture):
    status = _create_status_field(data_fixture, "single_select")
    twin = data_fixture.create_select_option(
        field=status.field, value="open", color="gray", order=2
    )

    result = update_fields(
        status.ctx,
        fields=[
            FieldItemUpdate(
                field_id=status.field.id,
                add_options=[SelectOptionCreate(value="New")],
                update_options=[
                    SelectOptionUpdate(id=twin.id, value="open", color="pink")
                ],
            )
        ],
        thought="add an option next to existing duplicates",
    )

    assert "errors" not in result
    assert [value for _, value, _ in _options(status)] == [
        "Open",
        "Closed",
        "open",
        "New",
    ]


@pytest.mark.parametrize(
    "model,kwargs",
    [
        (SelectOptionCreate, {}),
        (SelectOptionUpdate, {"id": 1}),
    ],
)
def test_select_option_values_fit_the_database_column(model, kwargs):
    model(value="x" * 255, **kwargs)
    with pytest.raises(ValidationError, match="at most 255 characters"):
        model(value="x" * 256, **kwargs)


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
    assert (error["item"], error["code"]) == (status.field.id, "invalid_input")
    assert message in error["message"]
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


def _fake_fixer(monkeypatch, fixed_formula, cancel=False):
    calls = []

    def make_fixer(user, workspace, tool_helpers):
        def fix(table, field_name, formula):
            calls.append((table.id, field_name, formula))
            if cancel:
                # The user cancels while the model is fixing this formula.
                tool_helpers.cancel()
            return fixed_formula

        return fix

    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.database.tools.make_formula_fixer",
        make_fixer,
    )
    return calls


@pytest.mark.django_db
def test_create_fields_repairs_a_formula_description(data_fixture, monkeypatch):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    calls = _fake_fixer(monkeypatch, "upper(field('Name'))")

    result = create_fields(
        make_test_ctx(user, workspace),
        table_id=table.id,
        fields=[
            FieldItemCreate(name="Loud", type="formula", formula="$formula: the name")
        ],
        thought="add formula",
    )

    assert calls == [(table.id, "Loud", "$formula: the name")]
    assert [field["name"] for field in result["created_fields"]] == ["Loud"]
    assert result["changed"] is True
    assert "error" not in result and "errors" not in result
    assert table.field_set.get(name="Loud").specific.formula == "upper(field('Name'))"


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["create", "update"])
def test_formula_repair_reports_an_unexpected_failure_as_failed(
    data_fixture, monkeypatch, action
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_formula_field(table=table, name="F", formula="'x'")
    _fake_fixer(monkeypatch, "'fixed'")
    messages = []
    sink_id = logger.add(
        lambda message: messages.append(message.record["message"]), level="ERROR"
    )
    real_update_field = shared_fields.update_field

    def update_field(tool_context, update):
        if update.formula == "'fixed'":
            raise RuntimeError("model down")
        return real_update_field(tool_context, update)

    create_action = MagicMock()
    create_action.do.side_effect = RuntimeError("model down")
    monkeypatch.setattr(helpers, "CreateFieldActionType", create_action)
    monkeypatch.setattr(helpers.shared_fields, "update_field", update_field)
    ctx = make_test_ctx(user, workspace)

    try:
        if action == "create":
            result = create_fields(
                ctx,
                table_id=table.id,
                fields=[FieldItemCreate(name="G", type="formula", formula="concat(")],
                thought="add formula",
            )
        else:
            result = update_fields(
                ctx,
                fields=[FieldItemUpdate(field_id=field.id, formula="concat(")],
                thought="fix formula",
            )
    finally:
        logger.remove(sink_id)

    (error,) = result["errors"]
    assert error["code"] == "failed"
    assert error["message"] == INTERNAL_ERROR_MESSAGE
    assert error["item"] == (field.id if action == "update" else "G")
    assert error["formula"] == "concat("
    assert "hint" not in error
    assert any("model down" in message for message in messages)


@pytest.mark.django_db
@pytest.mark.parametrize("fixed_formula", ["concat('a', 'b')", None])
def test_update_fields_repairs_an_invalid_formula(
    data_fixture, monkeypatch, fixed_formula
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_formula_field(table=table, name="F", formula="'x'")
    calls = _fake_fixer(monkeypatch, fixed_formula)

    result = update_fields(
        make_test_ctx(user, workspace),
        fields=[FieldItemUpdate(field_id=field.id, name="G", formula="concat(")],
        thought="fix formula",
    )

    assert calls == [(table.id, "G", "concat(")]
    field.refresh_from_db()
    if fixed_formula:
        assert result["changed"] is True
        assert result["updated_fields"][0]["formula"] == fixed_formula
        assert "errors" not in result
        assert (field.name, field.formula) == ("G", fixed_formula)
    else:
        assert result["changed"] is False
        assert result["updated_fields"] == []
        (error,) = result["errors"]
        assert (error["item"], error["code"]) == (field.id, "invalid_formula")
        assert (error["field_name"], error["formula"]) == ("G", "concat(")
        assert error["message"].startswith("Invalid syntax")
        assert "generate_formula" in error["hint"]
        assert result["error"]["code"] == "invalid_formula"
        assert (field.name, field.formula) == ("F", "'x'")


@pytest.mark.django_db
def test_shared_field_tools_stop_when_the_chat_is_cancelled(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, name="Kept")
    ctx = make_test_ctx(user, workspace)
    ctx.deps.tool_helpers.cancel()

    with pytest.raises(asyncio.CancelledError):
        delete_fields(ctx, field_ids=[field.id], thought="delete")

    assert Field.objects.filter(id=field.id).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("formula", ["", "  "])
def test_create_fields_does_not_ask_the_fixer_to_invent_a_formula(
    data_fixture, monkeypatch, formula
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    calls = _fake_fixer(monkeypatch, "'invented'")

    result = create_fields(
        make_test_ctx(user, workspace),
        table_id=table.id,
        fields=[FieldItemCreate(name="F", type="formula", formula=formula)],
        thought="add formula",
    )

    assert calls == []
    assert result["created_fields"] == []
    (error,) = result["errors"]
    assert (error["code"], error["field_name"], error["message"]) == (
        "invalid_formula",
        "F",
        "'F' needs a formula.",
    )
    assert not table.field_set.filter(name="F").exists()


@pytest.mark.django_db
def test_update_fields_does_not_ask_the_fixer_to_invent_a_formula(
    data_fixture, monkeypatch
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_formula_field(table=table, name="F", formula="'x'")
    calls = _fake_fixer(monkeypatch, "'invented'")

    result = update_fields(
        make_test_ctx(user, workspace),
        fields=[FieldItemUpdate(field_id=field.id, formula="")],
        thought="clear formula",
    )

    assert calls == []
    (error,) = result["errors"]
    assert (error["item"], error["code"], error["message"]) == (
        field.id,
        "invalid_formula",
        "'F' needs a formula.",
    )
    field.refresh_from_db()
    assert field.formula == "'x'"


@pytest.mark.django_db
def test_create_tables_notes_a_formula_field_without_a_formula(
    data_fixture, monkeypatch
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    calls = _fake_fixer(monkeypatch, "'invented'")

    result = create_tables(
        make_test_ctx(user, workspace),
        database_id=database.id,
        tables=[
            TableItemCreate(
                name="Orders",
                primary_field_name="Order",
                fields=[FieldItemCreate(name="Total", type="formula")],
            )
        ],
        add_sample_rows=False,
        thought="create Orders",
    )

    table = database.table_set.get(name="Orders")
    assert calls == []
    assert result["notes"] == [
        f"Formula field 'Total' in table_{table.id} was not created: it needs a "
        "formula."
    ]
    assert not table.field_set.filter(name="Total").exists()


@pytest.mark.django_db
def test_create_tables_notes_every_unrepaired_formula_after_a_denial(
    data_fixture, monkeypatch
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    _fake_fixer(monkeypatch, "'fixed'")
    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.database.helpers.CreateFieldActionType.do",
        MagicMock(side_effect=PermissionException()),
    )

    result = create_tables(
        make_test_ctx(user, workspace),
        database_id=database.id,
        tables=[
            TableItemCreate(
                name=name,
                primary_field_name="Name",
                fields=[
                    FieldItemCreate(name=f"{name} X", type="formula", formula="concat(")
                ],
            )
            for name in ("A", "B")
        ],
        add_sample_rows=False,
        thought="create A and B",
    )

    a = database.table_set.get(name="A")
    b = database.table_set.get(name="B")
    permission_note, *formula_notes = result["notes"]
    assert permission_note.startswith(
        f"Permission denied while creating fields in table_{a.id}."
    )
    assert [note.split(":")[0] for note in formula_notes] == [
        f"Invalid formula for field 'A X' in table_{a.id}",
        f"Invalid formula for field 'B X' in table_{b.id}",
    ]


@pytest.mark.django_db
def test_create_tables_keeps_the_repairs_made_before_a_denial(
    data_fixture, monkeypatch
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    _fake_fixer(monkeypatch, "'fixed'")
    original = CreateFieldActionType.do
    calls = []

    def do(user, table, field_type, **kwargs):
        calls.append(kwargs["name"])
        if len(calls) > 1:
            raise PermissionException()
        return original(user, table, field_type, **kwargs)

    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.database.helpers.CreateFieldActionType.do",
        do,
    )

    result = create_tables(
        make_test_ctx(user, workspace),
        database_id=database.id,
        tables=[
            TableItemCreate(
                name="A",
                primary_field_name="Name",
                fields=[
                    FieldItemCreate(name=n, type="formula", formula="concat(")
                    for n in ("A X", "A Y")
                ],
            ),
            TableItemCreate(
                name="B",
                primary_field_name="Name",
                fields=[FieldItemCreate(name="B X", type="formula", formula="concat(")],
            ),
        ],
        add_sample_rows=False,
        thought="create A and B",
    )

    a = database.table_set.get(name="A")
    b = database.table_set.get(name="B")
    assert a.field_set.get(name="A X").specific.formula == "'fixed'"
    permission_note, *formula_notes = result["notes"]
    assert permission_note.startswith(
        f"Permission denied while creating fields in table_{a.id}."
    )
    assert [note.split(":")[0] for note in formula_notes] == [
        f"Invalid formula for field 'A Y' in table_{a.id}",
        f"Invalid formula for field 'B X' in table_{b.id}",
    ]


@pytest.mark.django_db
def test_create_fields_drops_the_model_cached_in_a_failed_repair(
    data_fixture, monkeypatch
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    _fake_fixer(monkeypatch, "'fixed'")
    original = CreateFieldActionType.do

    def do(*args, **kwargs):
        original(*args, **kwargs)
        raise IntegrityError("duplicate key value")

    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.database.helpers.CreateFieldActionType.do",
        do,
    )

    result = create_fields(
        make_test_ctx(user, workspace),
        table_id=table.id,
        fields=[FieldItemCreate(name="F", type="formula", formula="concat(")],
        thought="add formula",
    )

    assert result["created_fields"] == []
    model = Table.objects.get(id=table.id).get_model()
    assert [f["field"].name for f in model._field_objects.values()] == ["Name"]


@pytest.mark.django_db
def test_update_fields_keeps_a_later_formula_for_the_same_field(
    data_fixture, monkeypatch
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_formula_field(table=table, name="F", formula="'x'")
    calls = _fake_fixer(monkeypatch, "'AI fix'")

    update_fields(
        make_test_ctx(user, workspace),
        fields=[
            FieldItemUpdate(field_id=field.id, name="G", formula="concat("),
            FieldItemUpdate(field_id=field.id, formula="'Final value'"),
        ],
        thought="test",
    )

    field.refresh_from_db()
    assert (field.name, field.formula) == ("G", "'Final value'")
    assert calls == []


@pytest.mark.django_db
def test_update_fields_repairs_a_formula_without_undoing_a_later_rename(
    data_fixture, monkeypatch
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_formula_field(table=table, name="F", formula="'x'")
    _fake_fixer(monkeypatch, "'AI fix'")

    update_fields(
        make_test_ctx(user, workspace),
        fields=[
            FieldItemUpdate(field_id=field.id, name="G", formula="concat("),
            FieldItemUpdate(field_id=field.id, name="H"),
        ],
        thought="test",
    )

    field.refresh_from_db()
    assert (field.name, field.formula) == ("H", "'AI fix'")


@pytest.mark.django_db
def test_update_fields_repairs_a_formula_a_later_update_leaves_unchanged(
    data_fixture, monkeypatch
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_formula_field(table=table, name="F", formula="'x'")
    calls = _fake_fixer(monkeypatch, "'AI fix'")

    update_fields(
        make_test_ctx(user, workspace),
        fields=[
            FieldItemUpdate(field_id=field.id, formula="concat("),
            FieldItemUpdate(field_id=field.id, name="H", formula=None),
        ],
        thought="test",
    )

    field.refresh_from_db()
    assert (field.name, field.formula) == ("H", "'AI fix'")
    assert calls == [(table.id, "F", "concat(")]


@pytest.mark.django_db
def test_update_fields_repairs_the_update_whose_formula_failed(
    data_fixture, monkeypatch
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    column = data_fixture.create_text_field(table=table, name="A")
    field = data_fixture.create_formula_field(table=table, name="F", formula="'x'")
    calls = _fake_fixer(monkeypatch, "field('B')")

    # The same formula is valid in the first update and invalid in the last one,
    # after A is renamed.
    update_fields(
        make_test_ctx(user, workspace),
        fields=[
            FieldItemUpdate(field_id=field.id, formula="field('A')"),
            FieldItemUpdate(field_id=column.id, name="B"),
            FieldItemUpdate(field_id=field.id, name="G", formula="field('A')"),
        ],
        thought="test",
    )

    field.refresh_from_db()
    assert (field.name, field.formula) == ("G", "field('B')")
    assert calls == [(table.id, "G", "field('A')")]


@pytest.mark.django_db
def test_create_fields_stops_repairing_formulas_when_cancelled(
    data_fixture, monkeypatch
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    calls = _fake_fixer(monkeypatch, "'fixed'", cancel=True)

    with pytest.raises(asyncio.CancelledError):
        create_fields(
            make_test_ctx(user, workspace),
            table_id=table.id,
            fields=[
                FieldItemCreate(name="A", type="formula", formula="concat("),
                FieldItemCreate(name="B", type="formula", formula="concat("),
            ],
            thought="test",
        )

    assert len(calls) == 1
    assert not table.field_set.filter(name__in=["A", "B"]).exists()


@pytest.mark.django_db
def test_update_fields_stops_repairing_formulas_when_cancelled(
    data_fixture, monkeypatch
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    a = data_fixture.create_formula_field(table=table, name="A", formula="'a'")
    b = data_fixture.create_formula_field(table=table, name="B", formula="'b'")
    calls = _fake_fixer(monkeypatch, "'fixed'", cancel=True)

    with pytest.raises(asyncio.CancelledError):
        update_fields(
            make_test_ctx(user, workspace),
            fields=[
                FieldItemUpdate(field_id=a.id, formula="concat("),
                FieldItemUpdate(field_id=b.id, formula="concat("),
            ],
            thought="test",
        )

    assert len(calls) == 1
    a.refresh_from_db()
    b.refresh_from_db()
    assert (a.formula, b.formula) == ("'a'", "'b'")


@pytest.mark.django_db
def test_create_tables_stops_repairing_formulas_when_cancelled(
    data_fixture, monkeypatch
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    calls = _fake_fixer(monkeypatch, "'fixed'", cancel=True)

    with pytest.raises(asyncio.CancelledError):
        create_tables(
            make_test_ctx(user, workspace),
            database_id=database.id,
            tables=[
                TableItemCreate(
                    name="T",
                    primary_field_name="Name",
                    fields=[
                        FieldItemCreate(name="A", type="formula", formula="concat("),
                        FieldItemCreate(name="B", type="formula", formula="concat("),
                    ],
                )
            ],
            add_sample_rows=False,
            thought="test",
        )

    assert len(calls) == 1
    table = Table.objects.get(database=database, name="T")
    assert not table.field_set.filter(name__in=["A", "B"]).exists()
