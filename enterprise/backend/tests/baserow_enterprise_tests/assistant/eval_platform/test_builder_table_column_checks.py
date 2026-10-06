import uuid
from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest

from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import TableElement
from baserow.contrib.builder.elements.service import ElementService
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.core.formula.types import BaserowFormulaObject
from baserow.test_utils.fixtures import Fixtures
from baserow_enterprise.assistant.evals.datasets.builder import (
    _check_adds_edit_button_column,
    _check_edits_table_columns,
    _check_keeps_link_column_settings,
    _check_moves_table_column,
)
from baserow_enterprise.assistant.evals.registry import get_case, get_scenario
from baserow_enterprise.assistant.evals.types import EvalRunOutput, EvalScenario

SCENARIO_NAME = "builder-edits-table-columns"

CASE_CHECKS = {
    "builder/edits-table-columns": _check_edits_table_columns,
    "builder/moves-table-column": _check_moves_table_column,
    "builder/keeps-link-column-settings": _check_keeps_link_column_settings,
    "builder/adds-edit-button-column": _check_adds_edit_button_column,
}

Columns = list[dict[str, Any]]


def _seed(data_fixture: Fixtures) -> EvalScenario:
    return get_scenario(SCENARIO_NAME)(data_fixture)


def _empty_output() -> EvalRunOutput:
    return EvalRunOutput(
        answer="",
        messages=[],
        tool_calls=[],
        tool_error_count=0,
        tool_error_hint="",
        sources=[],
        request_count=0,
        duration_s=0,
    )


def _stored_columns(scenario: EvalScenario) -> Columns:
    return [deepcopy(column._asdict()) for column in scenario.refs["before"]]


def _save_columns(scenario: EvalScenario, columns: Columns) -> TableElement:
    table_element = TableElement.objects.get(id=scenario.refs["table_element_id"])
    ElementHandler().update_element(table_element, fields=columns)
    return table_element


def _by_name(columns: Columns) -> dict[str, dict[str, Any]]:
    return {column["name"]: column for column in columns}


def _with_new_uids(columns: Columns) -> Columns:
    return [
        {key: value for key, value in column.items() if key != "uid"}
        for column in columns
    ]


def _with_link_as_text(columns: Columns) -> Columns:
    text_config = {"value": BaserowFormulaObject.create("''")}
    return [
        {**column, "type": "text", "config": text_config}
        if column["type"] == "link"
        else column
        for column in columns
    ]


def _without_adding_date(columns: Columns) -> Columns:
    return [column for column in columns if column["name"] != "Adding date"]


def _with_styles_reset(columns: Columns) -> Columns:
    return [{**column, "styles": {}} for column in columns]


@pytest.mark.django_db
def test_untouched_seed_passes_keep_checks_and_fails_change_checks(
    data_fixture: Fixtures,
) -> None:
    scenario = _seed(data_fixture)
    output = _empty_output()

    keeps = _check_keeps_link_column_settings(None, scenario, output)
    moves = _check_moves_table_column(None, scenario, output)
    edits = _check_edits_table_columns(None, scenario, output)
    adds = _check_adds_edit_button_column(None, scenario, output)

    assert all(check.passed for check in keeps), keeps
    assert not all(check.passed for check in moves)
    assert not all(check.passed for check in edits)
    assert not all(check.passed for check in adds)


@pytest.mark.django_db
def test_moves_check_passes_when_email_goes_after_website(
    data_fixture: Fixtures,
) -> None:
    scenario = _seed(data_fixture)
    columns = _by_name(_stored_columns(scenario))
    order = ["Name", "Adding date", "Website", "Email", "Edit"]

    _save_columns(scenario, [columns[name] for name in order])

    checks = _check_moves_table_column(None, scenario, _empty_output())
    assert all(check.passed for check in checks), checks


@pytest.mark.django_db
def test_edits_check_passes_when_the_columns_change_as_asked(
    data_fixture: Fixtures,
) -> None:
    scenario = _seed(data_fixture)
    joined_id = scenario.refs["joined_field"].id
    columns = _by_name(_stored_columns(scenario))
    columns["Name"]["name"] = "Full name"
    columns["Adding date"]["config"] = {
        "value": BaserowFormulaObject.create(f"get('current_record.field_{joined_id}')")
    }
    order = ["Name", "Adding date", "Website", "Edit", "Email"]

    _save_columns(scenario, [columns[name] for name in order])

    checks = _check_edits_table_columns(None, scenario, _empty_output())
    assert all(check.passed for check in checks), checks


@pytest.mark.django_db
def test_adds_check_passes_when_an_editar_button_opens_the_edit_page(
    data_fixture: Fixtures,
) -> None:
    scenario = _seed(data_fixture)
    new_uid = uuid.uuid4()
    editar = {
        "uid": str(new_uid),
        "name": "Editar",
        "type": "button",
        "config": {"label": BaserowFormulaObject.create("'Editar'")},
        "styles": {},
    }

    table_element = _save_columns(scenario, [*_stored_columns(scenario), editar])
    data_fixture.create_open_page_workflow_action(
        element=table_element,
        event=f"{new_uid}_click",
        navigation_type="page",
        navigate_to_page=scenario.refs["edit_page"],
        page_parameters=[
            {
                "name": "id",
                "value": BaserowFormulaObject.create("get('current_record.id')"),
            }
        ],
    )

    checks = _check_adds_edit_button_column(None, scenario, _empty_output())
    assert all(check.passed for check in checks), checks


@pytest.mark.django_db
@pytest.mark.parametrize(
    "damage",
    [
        _with_new_uids,
        _with_link_as_text,
        _without_adding_date,
        _with_styles_reset,
    ],
    ids=lambda damage: damage.__name__,
)
def test_keeps_check_fails_when_the_table_columns_are_damaged(
    data_fixture: Fixtures, damage: Callable[[Columns], Columns]
) -> None:
    scenario = _seed(data_fixture)

    _save_columns(scenario, damage(_stored_columns(scenario)))

    checks = _check_keeps_link_column_settings(None, scenario, _empty_output())
    assert not all(check.passed for check in checks)


@pytest.mark.django_db
@pytest.mark.parametrize("case_id", CASE_CHECKS)
def test_checks_fail_instead_of_raising_when_the_table_element_is_deleted(
    data_fixture: Fixtures, case_id: str
) -> None:
    scenario = _seed(data_fixture)
    table_element = TableElement.objects.get(id=scenario.refs["table_element_id"])
    ElementService().delete_element(scenario.user, table_element)

    checks = CASE_CHECKS[case_id](None, scenario, _empty_output())

    assert not all(check.passed for check in checks)


@pytest.mark.django_db
def test_seed_is_the_students_table_the_prompts_describe(
    data_fixture: Fixtures,
) -> None:
    scenario = _seed(data_fixture)
    refs = scenario.refs
    before = refs["before"]
    names = ["Name", "Email", "Adding date", "Website", "Edit"]

    assert [column.name for column in before] == names
    assert [column.type for column in before] == [
        "text",
        "text",
        "text",
        "link",
        "button",
    ]
    assert [column.uid for column in before] == [refs["uids"][name] for name in names]
    assert before[0].styles == {"cell": {"cell_font_color": "red"}}
    assert before[2].config == {
        "value": {"formula": "", "mode": "simple", "version": "0.1"}
    }
    action = BuilderWorkflowAction.objects.get(id=refs["edit_action_id"]).specific
    assert action.event == f"{refs['uids']['Edit']}_click"
    assert action.navigate_to_page_id == refs["edit_page"].id
    assert [parameter["name"] for parameter in action.page_parameters] == ["id"]
    table = refs["joined_field"].table
    db_columns = [field.db_column for field in table.field_set.all()]
    rows = list(table.get_model().objects.values(*db_columns))
    assert len(rows) == 2
    assert all(all(row.values()) for row in rows)


@pytest.mark.django_db
@pytest.mark.parametrize("case_id", CASE_CHECKS)
def test_case_uses_its_check_and_the_seeded_builder(
    data_fixture: Fixtures, case_id: str
) -> None:
    case = get_case(case_id)
    scenario = _seed(data_fixture)

    assert case.scenario == SCENARIO_NAME
    assert case.checks is CASE_CHECKS[case_id]
    assert scenario.refs["builder"].name in case.prompt
