"""Kuma changes a table element's columns one by one, by uid."""

from collections.abc import Callable
from typing import Any, NamedTuple
from unittest.mock import MagicMock

from django.db import DatabaseError, connection

import pytest
from pydantic import ValidationError

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.elements.actions import UpdateElementActionType
from baserow.contrib.builder.elements.models import TableElement
from baserow.contrib.builder.elements.operations import UpdateElementOperationType
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.table.models import Table
from baserow.contrib.integrations.local_baserow.models import LocalBaserowListRows
from baserow.core.action.models import Action
from baserow.core.exceptions import PermissionDenied
from baserow.core.formula.types import BaserowFormulaObject
from baserow.test_utils.fixtures import Fixtures
from baserow_enterprise.assistant.tools.builder.tools import update_element
from baserow_enterprise.assistant.tools.builder.types import (
    ElementUpdate,
    TableColumnUpdate,
)
from baserow_enterprise.assistant.tools.builder.types.table_columns import (
    data_source_fields,
)
from baserow_enterprise.assistant.tools.shared import ToolInputError
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role

from .utils import make_test_ctx

UNKNOWN_UID = "00000000-0000-0000-0000-000000000000"
STYLES = {"cell": {"cell_font_color": "red"}}
TYPE_MISFIT_GUIDANCE = (
    "value and field_id are for text, boolean and rating columns, and label for "
    "button columns; link, tags and image columns can only be renamed, reordered or "
    "removed here. No changes were applied."
)
NAME_CLASH_GUIDANCE = (
    "Leave out columns that already exist to keep them, or change them with "
    "update_table_columns by uid. No changes were applied."
)

Column = tuple[str, str, str, Any, Any]


class SeededTable(NamedTuple):
    ctx: MagicMock
    page: Page
    table: TableElement
    uids: dict[str, str]
    go_action: BuilderWorkflowAction
    email_field_id: int
    people: Table


def _formula(text: str) -> BaserowFormulaObject:
    return BaserowFormulaObject.create(text)


def _advanced(text: str) -> BaserowFormulaObject:
    return BaserowFormulaObject.create(text, mode="advanced")


@pytest.fixture
def seeded(data_fixture: Fixtures) -> SeededTable:
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    database = data_fixture.create_database_application(workspace=workspace)
    people = data_fixture.create_database_table(database=database, name="People")
    # The trailing space is a typo a column name must still match.
    email_field = data_fixture.create_text_field(table=people, name="Email ")
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=people
    )
    site_formula = _formula("get('current_record.field_3')")
    table = data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source,
        fields=[
            {
                "name": "Name",
                "type": "text",
                "config": {"value": _formula("get('current_record.field_1')")},
                "styles": STYLES,
            },
            {"name": "Note", "type": "text", "config": {"value": _formula("'hello'")}},
            {
                "name": "Site",
                "type": "link",
                "config": {
                    "navigation_type": "custom",
                    "navigate_to_url": site_formula,
                    "link_name": site_formula,
                    "target": "self",
                    "variant": "link",
                    "page_parameters": [],
                    "query_parameters": [],
                },
            },
            {"name": "Go", "type": "button", "config": {"label": _formula("'Go'")}},
            {
                "name": "Stars",
                "type": "rating",
                "config": {
                    "value": _formula("get('current_record.field_2')"),
                    "max_value": 5,
                    "color": "primary",
                },
            },
        ],
    )
    uids = {column.name: str(column.uid) for column in table.fields.all()}
    go_action = data_fixture.create_notification_workflow_action(
        element=table, event=f"{uids['Go']}_click"
    )
    return SeededTable(
        make_test_ctx(user, workspace),
        page,
        table,
        uids,
        go_action,
        email_field.id,
        people,
    )


@pytest.fixture
def people_fields(seeded: SeededTable, data_fixture: Fixtures) -> dict[str, Field]:
    people = seeded.people
    return {
        "text": data_fixture.create_text_field(table=people, name="Title"),
        "single_select": data_fixture.create_single_select_field(
            table=people, name="Status"
        ),
        "multiple_select": data_fixture.create_multiple_select_field(
            table=people, name="Tags"
        ),
        "link_row": data_fixture.create_link_row_field(table=people, name="Friends"),
        "created_by": data_fixture.create_created_by_field(table=people, name="Author"),
        "multiple_collaborators": data_fixture.create_multiple_collaborators_field(
            table=people, name="Owners"
        ),
        "number": data_fixture.create_number_field(table=people, name="Score"),
    }


def _columns(table: TableElement) -> list[Column]:
    return [
        (str(column.uid), column.name, column.type, column.config, column.styles)
        for column in table.fields.order_by("order", "id")
    ]


def _update(seeded: SeededTable, **properties: Any) -> dict[str, Any]:
    return update_element(
        seeded.ctx,
        page_id=seeded.page.id,
        element=ElementUpdate.model_validate(
            {"element_id": seeded.table.id, **properties}
        ),
        thought="Change the table's columns.",
    )


def _action_exists(action: BuilderWorkflowAction) -> bool:
    return BuilderWorkflowAction.objects.filter(id=action.id).exists()


def _assert_refused(seeded: SeededTable, message: str, **properties: Any) -> None:
    before = _columns(seeded.table)
    with pytest.raises(ToolInputError) as raised:
        _update(seeded, **properties)
    assert str(raised.value) == message
    assert _columns(seeded.table) == before
    assert _action_exists(seeded.go_action)


@pytest.mark.django_db
def test_renaming_a_column_changes_only_its_name(seeded: SeededTable) -> None:
    before = _columns(seeded.table)

    _update(
        seeded,
        update_table_columns=[{"uid": seeded.uids["Name"], "name": "Full name"}],
    )

    uid, _, column_type, config, styles = before[0]
    assert _columns(seeded.table) == [
        (uid, "Full name", column_type, config, styles),
        *before[1:],
    ]
    assert styles == STYLES
    assert _action_exists(seeded.go_action)


@pytest.mark.django_db
def test_renaming_a_button_column_keeps_its_click_actions(
    seeded: SeededTable,
) -> None:
    _update(seeded, update_table_columns=[{"uid": seeded.uids["Go"], "name": "Open"}])

    assert seeded.table.fields.get(uid=seeded.uids["Go"]).name == "Open"
    assert _action_exists(seeded.go_action)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value,stored",
    [
        ("new text", "'new text'"),
        ("get('current_record.field_9')", "get('current_record.field_9')"),
        ("", "''"),
        ("'quoted'", "'quoted'"),
    ],
)
def test_changing_a_column_value(seeded: SeededTable, value: str, stored: str) -> None:
    note = seeded.uids["Note"]
    before = _columns(seeded.table)

    _update(seeded, update_table_columns=[{"uid": note, "value": value}])

    after = _columns(seeded.table)
    assert after[1] == (note, "Note", "text", {"value": _advanced(stored)}, {})
    assert after[:1] + after[2:] == before[:1] + before[2:]


@pytest.mark.django_db
def test_a_column_update_changes_only_the_keys_sent(seeded: SeededTable) -> None:
    uids = seeded.uids
    before = {column[0]: column for column in _columns(seeded.table)}

    _update(
        seeded,
        update_table_columns=[
            {"uid": uids["Stars"], "value": "get('current_record.field_7')"},
            {"uid": uids["Site"], "name": "Website"},
        ],
    )

    after = {column[0]: column for column in _columns(seeded.table)}
    stars_config = before[uids["Stars"]][3]
    assert after[uids["Stars"]][3] == {
        **stars_config,
        "value": _advanced("get('current_record.field_7')"),
    }
    assert after[uids["Site"]] == (uids["Site"], "Website", *before[uids["Site"]][2:])


@pytest.mark.django_db
def test_a_formula_description_is_refused_on_update(seeded: SeededTable) -> None:
    _assert_refused(
        seeded,
        "Column 'Note' has a value that is not a valid formula. For fixed text, put "
        "it in single quotes; to show data, set field_id or use a runtime formula "
        "such as get('current_record.field_<id>'). \"$formula:\" descriptions are "
        "generated only when a table is created. No changes were applied.",
        update_table_columns=[
            {"uid": seeded.uids["Note"], "value": "$formula: the name"}
        ],
    )


@pytest.mark.django_db
def test_changing_a_button_label(seeded: SeededTable) -> None:
    _update(seeded, update_table_columns=[{"uid": seeded.uids["Go"], "label": "Open"}])

    go = seeded.table.fields.get(uid=seeded.uids["Go"])
    assert (go.name, go.config) == ("Go", {"label": _advanced("'Open'")})
    assert _action_exists(seeded.go_action)


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["upper('abc')", "  upper('abc') "])
def test_a_value_equal_to_the_stored_formula_keeps_it_as_stored(
    seeded: SeededTable, value: str
) -> None:
    stored = {"formula": "upper('abc')", "mode": "simple", "version": "0.1"}
    note = seeded.table.fields.get(uid=seeded.uids["Note"])
    note.config = {"value": dict(stored)}
    note.save()

    _update(
        seeded,
        update_table_columns=[
            {"uid": seeded.uids["Note"], "name": "Shout", "value": value}
        ],
    )

    note = seeded.table.fields.get(uid=seeded.uids["Note"])
    assert (note.name, note.config) == ("Shout", {"value": stored})


@pytest.mark.django_db
def test_reordering_columns(seeded: SeededTable) -> None:
    before = {column[0]: column for column in _columns(seeded.table)}
    order = [seeded.uids[name] for name in ("Stars", "Go", "Name", "Site", "Note")]

    _update(seeded, reorder_table_columns=order)

    assert _columns(seeded.table) == [before[uid] for uid in order]
    assert _action_exists(seeded.go_action)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "listed,removed,problems",
    [
        (["Name", "Note", "Site", "Go"], [], " Missing: {Stars} 'Stars'."),
        (
            ["Name", "Note", "Site", "Go", "Stars", "Note"],
            [],
            " Listed more than once: {Note} 'Note'.",
        ),
        (
            ["Name", "Note", "Site", "Go", "Stars"],
            ["Go"],
            " Removed in this call: {Go} 'Go'.",
        ),
        (
            ["Name", "Name", "Site", "Go", "Stars"],
            [],
            " Missing: {Note} 'Note'. Listed more than once: {Name} 'Name'.",
        ),
    ],
    ids=["missing", "repeated", "removed", "missing-and-repeated"],
)
def test_a_reorder_must_list_every_column_that_stays_once(
    seeded: SeededTable, listed: list[str], removed: list[str], problems: str
) -> None:
    _assert_refused(
        seeded,
        "reorder_table_columns must list every column that stays exactly once."
        f"{problems.format(**seeded.uids)} No changes were applied.",
        reorder_table_columns=[seeded.uids[name] for name in listed],
        remove_table_columns=[seeded.uids[name] for name in removed],
    )


@pytest.mark.django_db
def test_new_columns_go_last_in_the_order_sent(seeded: SeededTable) -> None:
    before = _columns(seeded.table)

    _update(
        seeded,
        add_table_columns=[
            {"name": "First", "value": "a"},
            {"name": "Second", "type": "button", "label": "Open"},
        ],
    )

    after = _columns(seeded.table)
    assert after[:5] == before
    assert [column[1:] for column in after[5:]] == [
        ("First", "text", {"value": _advanced("'a'")}, {}),
        ("Second", "button", {"label": _advanced("'Open'")}, {}),
    ]
    assert _action_exists(seeded.go_action)


@pytest.mark.django_db
def test_new_columns_go_before_their_anchor_in_the_order_sent(
    seeded: SeededTable,
) -> None:
    before = _columns(seeded.table)
    go = seeded.uids["Go"]

    _update(
        seeded,
        add_table_columns=[
            {"name": "A", "value": "a", "before_uid": go},
            {"name": "Last", "value": "z"},
            {"name": "B", "value": "b", "before_uid": go.upper()},
        ],
    )

    after = _columns(seeded.table)
    assert [column[1] for column in after] == [
        "Name",
        "Note",
        "Site",
        "A",
        "B",
        "Go",
        "Stars",
        "Last",
    ]
    assert [column for column in after if column in before] == before


@pytest.mark.django_db
def test_a_new_button_column_is_labelled_with_its_name(seeded: SeededTable) -> None:
    _update(seeded, add_table_columns=[{"name": "Edit", "type": "button"}])

    edit = seeded.table.fields.get(name="Edit")
    assert (edit.type, edit.config) == ("button", {"label": _advanced("'Edit'")})


@pytest.mark.django_db
def test_a_new_text_column_shows_the_field_named_like_it(seeded: SeededTable) -> None:
    _update(
        seeded,
        add_table_columns=[{"name": " EMAIL "}, {"name": "Phone", "value": ""}],
    )

    email = seeded.table.fields.get(name=" EMAIL ")
    phone = seeded.table.fields.get(name="Phone")
    field_formula = f"get('current_record.field_{seeded.email_field_id}')"
    assert email.config == {"value": _advanced(field_formula)}
    assert phone.config == {"value": _advanced("''")}


@pytest.mark.django_db
def test_removing_a_button_column_deletes_its_click_actions(
    seeded: SeededTable,
) -> None:
    go = seeded.uids["Go"]
    before = _columns(seeded.table)

    result = _update(seeded, remove_table_columns=[go])

    assert _columns(seeded.table) == [column for column in before if column[0] != go]
    assert not _action_exists(seeded.go_action)
    assert result["removed_table_columns"] == [
        {"uid": go, "name": "Go", "type": "button", "deleted_click_actions": 1}
    ]


@pytest.mark.django_db
def test_removing_one_of_two_same_named_columns_keeps_the_other(
    data_fixture: Fixtures,
) -> None:
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    table = data_fixture.create_builder_table_element(
        page=page,
        fields=[
            {"name": "Edit", "type": "button", "config": {"label": "'Edit'"}},
            {"name": "Edit", "type": "button", "config": {"label": "'Edit'"}},
        ],
    )
    first, second = [str(column.uid) for column in table.fields.all()]
    first_action, second_action = [
        data_fixture.create_notification_workflow_action(
            element=table, event=f"{uid}_click"
        )
        for uid in (first, second)
    ]

    update_element(
        make_test_ctx(user, workspace),
        page_id=page.id,
        element=ElementUpdate(element_id=table.id, remove_table_columns=[first]),
        thought="Remove the first Edit column.",
    )

    assert [str(column.uid) for column in table.fields.all()] == [second]
    assert not _action_exists(first_action)
    assert _action_exists(second_action)


@pytest.mark.django_db
def test_the_result_lists_the_columns_after_the_write(seeded: SeededTable) -> None:
    uids = seeded.uids

    result = _update(
        seeded,
        add_table_columns=[{"name": "Email"}],
        update_table_columns=[{"uid": uids["Name"], "name": "Full name"}],
    )

    email_uid = str(seeded.table.fields.get(name="Email").uid)
    assert result["updated_fields"] == ["add_table_columns", "update_table_columns"]
    assert result["table_columns"] == [
        {
            "uid": uids["Name"],
            "name": "Full name",
            "type": "text",
            "value": "get('current_record.field_1')",
        },
        {"uid": uids["Note"], "name": "Note", "type": "text", "value": "'hello'"},
        {"uid": uids["Site"], "name": "Site", "type": "link"},
        {"uid": uids["Go"], "name": "Go", "type": "button", "label": "'Go'"},
        {
            "uid": uids["Stars"],
            "name": "Stars",
            "type": "rating",
            "value": "get('current_record.field_2')",
        },
        {
            "uid": email_uid,
            "name": "Email",
            "type": "text",
            "value": f"get('current_record.field_{seeded.email_field_id}')",
        },
    ]
    assert "removed_table_columns" not in result


@pytest.mark.django_db
def test_all_changes_of_a_call_are_saved_as_one_undoable_action(
    seeded: SeededTable,
) -> None:
    uids = seeded.uids
    actions_before = Action.objects.filter(type=UpdateElementActionType.type).count()

    result = _update(
        seeded,
        items_per_page=3,
        remove_table_columns=[uids["Stars"]],
        update_table_columns=[{"uid": uids["Note"], "name": "Memo"}],
        reorder_table_columns=[uids["Go"], uids["Note"], uids["Name"], uids["Site"]],
        add_table_columns=[{"name": "New", "value": "n", "before_uid": uids["Go"]}],
    )

    assert [column[1] for column in _columns(seeded.table)] == [
        "New",
        "Go",
        "Memo",
        "Name",
        "Site",
    ]
    assert TableElement.objects.get(id=seeded.table.id).items_per_page == 3
    assert result["removed_table_columns"] == [
        {"uid": uids["Stars"], "name": "Stars", "type": "rating"}
    ]
    actions_after = Action.objects.filter(type=UpdateElementActionType.type).count()
    assert actions_after == actions_before + 1


@pytest.mark.django_db
def test_a_name_freed_in_the_same_call_can_be_reused(seeded: SeededTable) -> None:
    uids = seeded.uids

    _update(
        seeded,
        update_table_columns=[
            {"uid": uids["Name"], "name": "Full name"},
            {"uid": uids["Note"], "name": "name"},
        ],
    )

    names = {str(column.uid): column.name for column in seeded.table.fields.all()}
    assert (names[uids["Name"]], names[uids["Note"]]) == ("Full name", "name")


@pytest.mark.django_db
def test_blank_names_never_clash(seeded: SeededTable) -> None:
    _update(
        seeded,
        add_table_columns=[{"name": "", "value": "a"}, {"name": " ", "value": "b"}],
    )

    assert [column[1] for column in _columns(seeded.table)][-2:] == ["", " "]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "properties,unknown",
    [
        ({"update_table_columns": [{"uid": UNKNOWN_UID, "name": "X"}]}, UNKNOWN_UID),
        ({"remove_table_columns": [UNKNOWN_UID]}, UNKNOWN_UID),
        ({"reorder_table_columns": [UNKNOWN_UID]}, UNKNOWN_UID),
        (
            {"add_table_columns": [{"name": "X", "before_uid": UNKNOWN_UID}]},
            UNKNOWN_UID,
        ),
        ({"remove_table_columns": ["Note"]}, "Note"),
    ],
    ids=["update", "remove", "reorder", "before_uid", "name-instead-of-uid"],
)
def test_an_unknown_uid_is_refused_with_the_columns_to_use(
    seeded: SeededTable, properties: dict[str, Any], unknown: str
) -> None:
    uids = seeded.uids
    _assert_refused(
        seeded,
        f"Columns ['{unknown}'] are not columns of table element {seeded.table.id}. "
        f"Its columns are: {uids['Name']} 'Name' (text), {uids['Note']} 'Note' "
        f"(text), {uids['Site']} 'Site' (link), {uids['Go']} 'Go' (button), "
        f"{uids['Stars']} 'Stars' (rating). Use these uids. No changes were applied.",
        **properties,
    )


@pytest.mark.django_db
def test_the_columns_listed_on_an_unknown_uid_stop_after_25(
    data_fixture: Fixtures,
) -> None:
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    table = data_fixture.create_builder_table_element(
        page=page,
        fields=[
            {"name": f"C{index}", "type": "text", "config": {"value": "''"}}
            for index in range(27)
        ],
    )
    uids = [str(column.uid) for column in table.fields.all()]

    with pytest.raises(ToolInputError) as raised:
        update_element(
            make_test_ctx(user, workspace),
            page_id=page.id,
            element=ElementUpdate(element_id=table.id, remove_table_columns=["C26"]),
            thought="Remove the last column.",
        )

    first_25 = ", ".join(
        f"{uid} 'C{index}' (text)" for index, uid in enumerate(uids[:25])
    )
    assert str(raised.value) == (
        f"Columns ['C26'] are not columns of table element {table.id}. Its columns "
        f"are: {first_25}, and 2 more (see list_elements). Use these uids. No "
        "changes were applied."
    )


@pytest.mark.django_db
def test_a_uid_shared_by_two_columns_is_refused(seeded: SeededTable) -> None:
    shared = seeded.uids["Note"]
    seeded.table.fields.filter(name="Stars").update(uid=shared)

    _assert_refused(
        seeded,
        f"Columns ['{shared}'] of table element {seeded.table.id} share a uid with "
        "another column, so they can't be told apart. Remove one of them in the "
        "table's editor, then retry. No changes were applied.",
        update_table_columns=[{"uid": shared, "name": "Memo"}],
    )


@pytest.mark.django_db
def test_a_column_changed_twice_is_refused(seeded: SeededTable) -> None:
    note = seeded.uids["Note"]

    _assert_refused(
        seeded,
        f"Columns ['{note}'] are changed more than once. Put all changes to a column "
        "in one update_table_columns entry. No changes were applied.",
        update_table_columns=[
            {"uid": note, "name": "Memo"},
            {"uid": note.upper(), "value": "b"},
        ],
    )


@pytest.mark.django_db
def test_a_column_changed_and_removed_is_refused(seeded: SeededTable) -> None:
    note = seeded.uids["Note"]

    _assert_refused(
        seeded,
        f"Columns ['{note}'] cannot be changed and removed. No changes were applied.",
        update_table_columns=[{"uid": note, "name": "Memo"}],
        remove_table_columns=[note],
    )


@pytest.mark.django_db
def test_a_new_column_cannot_be_placed_before_a_removed_one(
    seeded: SeededTable,
) -> None:
    note = seeded.uids["Note"]

    _assert_refused(
        seeded,
        f"Columns ['{note}'] are removed in this call, so new columns can't be "
        "placed before them. No changes were applied.",
        remove_table_columns=[note],
        add_table_columns=[{"name": "Memo", "value": "m", "before_uid": note}],
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name,column_type,key",
    [("Go", "button", "value"), ("Note", "text", "label"), ("Site", "link", "value")],
)
def test_a_key_that_does_not_fit_the_column_type_is_refused(
    seeded: SeededTable, name: str, column_type: str, key: str
) -> None:
    uid = seeded.uids[name]

    _assert_refused(
        seeded,
        f"These changes don't fit the column type: column {uid} '{name}' is a "
        f"{column_type} column, so {key} does not apply. {TYPE_MISFIT_GUIDANCE}",
        update_table_columns=[{"uid": uid, key: "x"}],
    )


@pytest.mark.django_db
def test_a_key_that_does_not_fit_a_new_column_is_refused(seeded: SeededTable) -> None:
    _assert_refused(
        seeded,
        "These changes don't fit the column type: the new column 'Edit' is a button "
        "column, so value does not apply; the new column 'Memo' is a text column, so "
        f"label does not apply. {TYPE_MISFIT_GUIDANCE}",
        add_table_columns=[
            {"name": "Edit", "type": "button", "value": "x"},
            {"name": "Memo", "label": "y"},
        ],
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "shows",
    [{"value": "x"}, {}, {"field_id": 0}],
    ids=["value", "no-value", "unknown-field-id"],
)
def test_a_new_column_named_like_an_existing_one_is_refused(
    seeded: SeededTable, shows: dict[str, Any]
) -> None:
    _assert_refused(
        seeded,
        "These columns would share a name (case and surrounding spaces are "
        f"ignored): column {seeded.uids['Note']} 'Note' and the new column ' note '. "
        f"{NAME_CLASH_GUIDANCE}",
        add_table_columns=[{"name": " note ", **shows}],
    )


@pytest.mark.django_db
def test_renaming_a_column_to_a_taken_name_is_refused(seeded: SeededTable) -> None:
    uids = seeded.uids
    seeded.table.fields.filter(name="Stars").update(name="GO")

    _assert_refused(
        seeded,
        "These columns would share a name (case and surrounding spaces are "
        f"ignored): column {uids['Name']} renamed to 'site' and column "
        f"{uids['Site']} 'Site'. {NAME_CLASH_GUIDANCE}",
        update_table_columns=[{"uid": uids["Name"], "name": "site"}],
    )


@pytest.mark.django_db
def test_a_column_removed_and_added_again_is_refused(seeded: SeededTable) -> None:
    note = seeded.uids["Note"]

    _assert_refused(
        seeded,
        f"Column {note} 'Note' is removed and added again, which would give it a new "
        "uid and drop its styles and click actions. To move it, use "
        "reorder_table_columns; to change it, use update_table_columns. No changes "
        "were applied.",
        remove_table_columns=[note],
        add_table_columns=[{"name": "NOTE", "value": "'bye'"}],
    )


@pytest.mark.django_db
def test_a_column_removed_and_added_again_without_a_value_is_refused(
    seeded: SeededTable,
) -> None:
    name = seeded.uids["Name"]

    _assert_refused(
        seeded,
        f"Column {name} 'Name' is removed and added again, which would give it a new "
        "uid and drop its styles and click actions. To move it, use "
        "reorder_table_columns; to change it, use update_table_columns. No changes "
        "were applied.",
        remove_table_columns=[name],
        add_table_columns=[{"name": "Name"}],
    )


@pytest.mark.django_db
def test_removing_every_column_is_refused(seeded: SeededTable) -> None:
    _assert_refused(
        seeded,
        f"Table element {seeded.table.id} would have no columns left. Keep a column, "
        "or add one with add_table_columns in the same call. No changes were "
        "applied.",
        remove_table_columns=list(seeded.uids.values()),
    )


@pytest.mark.django_db
@pytest.mark.parametrize("change", ["echo", "same-order"])
def test_a_call_that_changes_nothing_is_refused(
    seeded: SeededTable, change: str
) -> None:
    uids = seeded.uids
    properties = (
        {
            "update_table_columns": [
                {"uid": uids["Note"], "name": "Note", "value": " 'hello' "},
                {"uid": uids["Go"], "label": "'Go'"},
            ]
        }
        if change == "echo"
        else {"reorder_table_columns": list(uids.values())}
    )

    _assert_refused(
        seeded,
        f"No column of table element {seeded.table.id} would change: the names, "
        "values and labels you sent are already stored, and the order is the same. "
        "Columns you don't list stay as they are; to move columns, use "
        "reorder_table_columns. No changes were applied.",
        **properties,
    )


@pytest.mark.django_db
def test_a_refused_column_change_applies_no_other_property(
    seeded: SeededTable,
) -> None:
    items_per_page = seeded.table.items_per_page

    with pytest.raises(ToolInputError):
        _update(seeded, items_per_page=items_per_page + 1, remove_table_columns=["X"])

    assert TableElement.objects.get(id=seeded.table.id).items_per_page == (
        items_per_page
    )


@pytest.mark.django_db
def test_an_unsupported_property_refuses_the_column_changes_too(
    seeded: SeededTable,
) -> None:
    before = _columns(seeded.table)

    with pytest.raises(ToolInputError) as raised:
        _update(
            seeded,
            orientation="horizontal",
            update_table_columns=[{"uid": seeded.uids["Note"], "name": "Memo"}],
        )

    message = str(raised.value)
    assert message.startswith(
        "Unsupported properties for table: orientation. No changes were applied."
    )
    supported = message.split("Supported properties include: ")[1].rstrip(".")
    assert {
        "add_table_columns",
        "update_table_columns",
        "reorder_table_columns",
        "remove_table_columns",
    } <= set(supported.split(", "))
    assert _columns(seeded.table) == before


@pytest.mark.django_db
def test_a_user_who_cannot_update_the_table_is_not_shown_its_columns(
    seeded: SeededTable,
    enterprise_data_fixture: Any,
    enable_enterprise: None,
    synced_roles: None,
) -> None:
    workspace = seeded.ctx.deps.workspace
    user = enterprise_data_fixture.create_user()
    enterprise_data_fixture.create_user_workspace(
        user=user, workspace=workspace, permissions="NO_ACCESS"
    )
    role = Role.objects.create(
        name="Read elements without updates", workspace=workspace
    )
    role.operations.set(
        Role.objects.get(uid="BUILDER").operations.exclude(
            name=UpdateElementOperationType.type
        )
    )
    RoleAssignmentHandler._init = False
    RoleAssignmentHandler().assign_role(
        user, workspace, role=role, scope=seeded.page.builder.application_ptr
    )

    with pytest.raises(PermissionDenied):
        update_element(
            make_test_ctx(user, workspace),
            page_id=seeded.page.id,
            element=ElementUpdate(
                element_id=seeded.table.id, remove_table_columns=[UNKNOWN_UID]
            ),
            thought="Remove a column.",
        )


@pytest.mark.django_db
def test_empty_column_lists_count_as_not_set(seeded: SeededTable) -> None:
    before = _columns(seeded.table)

    result = _update(
        seeded,
        items_per_page=3,
        add_table_columns=[],
        update_table_columns=[],
        reorder_table_columns=[],
        remove_table_columns=[],
    )

    assert result["updated_fields"] == ["items_per_page"]
    assert "table_columns" not in result
    assert _columns(seeded.table) == before


@pytest.mark.parametrize("replaced", ["fields", "add_fields", "remove_fields"])
def test_column_lists_cannot_be_replaced_by_name(replaced: str) -> None:
    with pytest.raises(ValidationError):
        ElementUpdate.model_validate({"element_id": 1, replaced: []})


def test_a_column_update_must_change_something() -> None:
    with pytest.raises(
        ValidationError, match="Column c1 needs a new name, value, field_id or label."
    ):
        TableColumnUpdate.model_validate({"uid": "c1"})


def test_a_field_id_alone_is_a_column_change() -> None:
    assert TableColumnUpdate.model_validate({"uid": "c1", "field_id": 5}).field_id == 5


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_type,path_suffix",
    [
        ("text", ""),
        ("single_select", ".value"),
        ("multiple_select", ".*.value"),
        ("link_row", ".*.value"),
        ("created_by", ".name"),
        ("multiple_collaborators", ".*.name"),
    ],
)
def test_a_field_id_shows_the_field_with_the_path_its_type_needs(
    seeded: SeededTable,
    people_fields: dict[str, Field],
    field_type: str,
    path_suffix: str,
) -> None:
    note = seeded.uids["Note"]
    field_id = people_fields[field_type].id
    before = _columns(seeded.table)

    _update(seeded, update_table_columns=[{"uid": note, "field_id": field_id}])

    shown = _advanced(f"get('current_record.field_{field_id}{path_suffix}')")
    after = _columns(seeded.table)
    assert after[1] == (note, "Note", "text", {"value": shown}, {})
    assert after[:1] + after[2:] == before[:1] + before[2:]


@pytest.mark.django_db
def test_a_new_column_with_a_field_id_shows_that_field_whatever_its_name(
    seeded: SeededTable, people_fields: dict[str, Field]
) -> None:
    status_id = people_fields["single_select"].id

    _update(seeded, add_table_columns=[{"name": "Anything", "field_id": status_id}])

    anything = seeded.table.fields.get(name="Anything")
    assert anything.config == {
        "value": _advanced(f"get('current_record.field_{status_id}.value')")
    }


@pytest.mark.django_db
def test_a_field_id_changes_only_the_value_of_a_rating_column(
    seeded: SeededTable, people_fields: dict[str, Field]
) -> None:
    rating_settings = {"max_value": 10, "color": "secondary", "rating_style": "heart"}
    stars = seeded.table.fields.get(uid=seeded.uids["Stars"])
    stars.config = {**stars.config, **rating_settings}
    stars.save()
    score_id = people_fields["number"].id

    _update(
        seeded,
        update_table_columns=[{"uid": seeded.uids["Stars"], "field_id": score_id}],
    )

    stars = seeded.table.fields.get(uid=seeded.uids["Stars"])
    assert stars.config == {
        "value": _advanced(f"get('current_record.field_{score_id}')"),
        **rating_settings,
    }


@pytest.mark.django_db
def test_a_field_id_the_column_already_shows_keeps_its_value_as_stored(
    seeded: SeededTable, people_fields: dict[str, Field]
) -> None:
    title_id = people_fields["text"].id
    stored = {
        "formula": f"get('current_record.field_{title_id}')",
        "mode": "simple",
        "version": "0.1",
    }
    note = seeded.table.fields.get(uid=seeded.uids["Note"])
    note.config = {"value": dict(stored)}
    note.save()

    _update(
        seeded,
        update_table_columns=[
            {"uid": seeded.uids["Note"], "name": "Title", "field_id": title_id}
        ],
    )

    note = seeded.table.fields.get(uid=seeded.uids["Note"])
    assert (note.name, note.config) == ("Title", {"value": stored})


@pytest.mark.django_db
def test_a_column_change_with_a_value_and_a_field_id_is_refused(
    seeded: SeededTable, people_fields: dict[str, Field]
) -> None:
    note = seeded.uids["Note"]

    _assert_refused(
        seeded,
        f"Column {note} 'Note' has both value and field_id. Set only one. No changes "
        "were applied.",
        update_table_columns=[
            {"uid": note, "value": "x", "field_id": people_fields["text"].id}
        ],
    )


@pytest.mark.django_db
def test_a_new_column_with_a_value_and_a_field_id_is_refused(
    seeded: SeededTable, people_fields: dict[str, Field]
) -> None:
    _assert_refused(
        seeded,
        "The new column 'Memo' has both value and field_id. Set only one. No changes "
        "were applied.",
        add_table_columns=[
            {"name": "Memo", "value": "x", "field_id": people_fields["text"].id}
        ],
    )


@pytest.mark.django_db
def test_a_field_id_that_does_not_fit_the_column_type_is_refused(
    seeded: SeededTable, people_fields: dict[str, Field]
) -> None:
    uids = seeded.uids
    title_id = people_fields["text"].id

    _assert_refused(
        seeded,
        f"These changes don't fit the column type: column {uids['Site']} 'Site' is a "
        f"link column, so field_id does not apply; column {uids['Go']} 'Go' is a "
        "button column, so field_id does not apply; the new column 'Edit' is a "
        f"button column, so field_id does not apply. {TYPE_MISFIT_GUIDANCE}",
        update_table_columns=[
            {"uid": uids["Site"], "field_id": title_id},
            {"uid": uids["Go"], "field_id": title_id},
        ],
        add_table_columns=[{"name": "Edit", "type": "button", "field_id": title_id}],
    )


def _remove_the_data_source(seeded: SeededTable, data_fixture: Fixtures) -> None:
    TableElement.objects.filter(id=seeded.table.id).update(data_source=None)


def _trash_the_data_source(seeded: SeededTable, data_fixture: Fixtures) -> None:
    DataSource.objects.filter(id=seeded.table.data_source_id).update(trashed=True)


def _remove_the_service(seeded: SeededTable, data_fixture: Fixtures) -> None:
    DataSource.objects.filter(id=seeded.table.data_source_id).update(service=None)


def _remove_the_service_table(seeded: SeededTable, data_fixture: Fixtures) -> None:
    LocalBaserowListRows.objects.filter(id=seeded.table.data_source.service_id).update(
        table=None
    )


def _switch_to_an_http_request_service(
    seeded: SeededTable, data_fixture: Fixtures
) -> None:
    DataSource.objects.filter(id=seeded.table.data_source_id).update(
        service=data_fixture.create_core_http_request_service()
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "drop_table",
    [
        _remove_the_data_source,
        _trash_the_data_source,
        _remove_the_service,
        _remove_the_service_table,
        _switch_to_an_http_request_service,
    ],
    ids=["no-data-source", "trashed", "no-service", "no-table", "http-request"],
)
def test_a_field_id_needs_a_data_source_with_a_table(
    seeded: SeededTable,
    people_fields: dict[str, Field],
    data_fixture: Fixtures,
    drop_table: Callable[[SeededTable, Fixtures], None],
) -> None:
    drop_table(seeded, data_fixture)

    _assert_refused(
        seeded,
        f"Table element {seeded.table.id} has no data source with a database table, "
        "so field_id can't be used. Set value instead. No changes were applied.",
        update_table_columns=[
            {"uid": seeded.uids["Note"], "field_id": people_fields["text"].id}
        ],
    )


@pytest.mark.django_db
def test_a_field_id_of_another_table_is_refused(
    seeded: SeededTable, data_fixture: Fixtures
) -> None:
    other = data_fixture.create_database_table(database=seeded.people.database)
    elsewhere = data_fixture.create_text_field(table=other, name="Elsewhere")
    missing_id = elsewhere.id + 1000

    _assert_refused(
        seeded,
        f"Fields [{elsewhere.id}, {missing_id}] are not fields of table "
        f"{seeded.people.id} 'People', which the data source of table element "
        f"{seeded.table.id} reads. Use field ids of that table from get_tables_schema. "
        "No changes were applied.",
        update_table_columns=[{"uid": seeded.uids["Note"], "field_id": elsewhere.id}],
        add_table_columns=[
            {"name": "Memo", "field_id": missing_id},
            {"name": "Copy", "field_id": elsewhere.id},
        ],
    )


@pytest.mark.django_db
def test_a_new_text_column_without_a_field_named_like_it_is_refused(
    seeded: SeededTable,
) -> None:
    _assert_refused(
        seeded,
        f"The new column 'Phone' would be empty: table {seeded.people.id} 'People' "
        "has no field named 'Phone'. Set field_id (from get_tables_schema) or value; "
        "value '' keeps it empty on purpose. No changes were applied.",
        add_table_columns=[{"name": "Phone"}],
    )


@pytest.mark.django_db
def test_a_new_text_column_without_a_data_source_is_refused(
    seeded: SeededTable, data_fixture: Fixtures
) -> None:
    _remove_the_data_source(seeded, data_fixture)

    _assert_refused(
        seeded,
        f"The new column 'Email' would be empty because table element "
        f"{seeded.table.id} has no data source. Set value. No changes were applied.",
        add_table_columns=[{"name": "Email"}],
    )


@pytest.mark.django_db
def test_a_database_error_reading_the_data_source_is_not_swallowed(
    seeded: SeededTable,
) -> None:
    def fail_on_data_sources(
        execute: Callable[..., Any],
        sql: str,
        params: Any,
        many: bool,
        context: dict[str, Any],
    ) -> Any:
        if "builder_datasource" in sql:
            raise DatabaseError("The connection was lost.")
        return execute(sql, params, many, context)

    with connection.execute_wrapper(fail_on_data_sources):
        with pytest.raises(DatabaseError):
            data_source_fields(seeded.table.data_source_id)
