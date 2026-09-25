"""Prod-replay checks score saved values, without calling a model."""

from typing import Any

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import FormulaField
from baserow.contrib.database.rows.handler import RowHandler
from baserow_enterprise.assistant.evals.datasets.prod_replay import (
    _check_fake_rows_into_typed_fields,
    _check_form_for_table_with_formula_field,
    _check_impossible_formula_request,
    _check_iso_week_number_formula,
    _check_page_inspection_existing_elements,
    _check_project_tracker_onboarding,
    _check_signed_amount_formula,
    _fake_rows_into_typed_fields_scenario,
    _form_for_table_with_formula_field_scenario,
    _impossible_formula_request_scenario,
    _iso_week_number_formula_scenario,
    _page_inspection_existing_elements_scenario,
    _project_tracker_onboarding_scenario,
    _signed_amount_formula_scenario,
)
from baserow_enterprise.assistant.evals.types import CheckResult, EvalRunOutput


def _output(**overrides: Any) -> EvalRunOutput:
    values = {
        "answer": "Done.",
        "messages": [],
        "tool_calls": [],
        "tool_error_count": 0,
        "tool_error_hint": "",
        "sources": [],
        "request_count": 1,
        "duration_s": 0,
    }
    return EvalRunOutput(**(values | overrides))


def _failed(checks: list[CheckResult]) -> set[str]:
    return {check.name for check in checks if not check.passed}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "enabled_fields, failed",
    [
        (("Customer", "Price"), set()),
        (("Customer",), {"form collects Customer and Price"}),
        (None, {"form view created", "form collects Customer and Price"}),
    ],
)
def test_form_check_requires_a_form_that_collects_the_order_fields(
    data_fixture, enabled_fields, failed
):
    scenario = _form_for_table_with_formula_field_scenario(data_fixture)
    table = scenario.refs["table"]
    if enabled_fields is not None:
        form = data_fixture.create_form_view(table=table)
        for field in table.field_set.filter(name__in=enabled_fields):
            data_fixture.create_form_view_field_option(form, field, enabled=True)

    checks = _check_form_for_table_with_formula_field(None, scenario, _output())

    assert _failed(checks) == failed


@pytest.mark.django_db
@pytest.mark.parametrize(
    "inspected, failed", [(True, set()), (False, {"page elements inspected"})]
)
def test_page_inspection_check_requires_listing_the_elements(
    data_fixture, inspected, failed
):
    scenario = _page_inspection_existing_elements_scenario(data_fixture)
    messages = [
        {
            "role": "assistant",
            "type": "ToolCallPart",
            "tool_name": "list_elements",
            "tool_call_id": "inspect",
            "args": {},
        }
    ]

    checks = _check_page_inspection_existing_elements(
        None, scenario, _output(messages=messages if inspected else [])
    )

    assert _failed(checks) == failed


@pytest.mark.django_db
@pytest.mark.parametrize(
    "row_counts, failed",
    [
        ({"Projects": 2, "Milestones": 3}, set()),
        ({"Projects": 2, "Milestones": 0}, {"every table has example rows"}),
        ({"Projects": 2}, {"Projects and Milestones tables created"}),
    ],
)
def test_onboarding_check_requires_the_requested_tables_with_rows(
    data_fixture, row_counts, failed
):
    scenario = _project_tracker_onboarding_scenario(data_fixture)
    for name, row_count in row_counts.items():
        table = data_fixture.create_database_table(
            database=scenario.refs["database"], name=name
        )
        primary = data_fixture.create_text_field(table=table, name="Name", primary=True)
        if row_count:
            RowHandler().force_create_rows(
                scenario.user,
                table,
                [{primary.db_column: f"{name} {i}"} for i in range(row_count)],
            )

    checks = _check_project_tracker_onboarding(None, scenario, _output())

    assert _failed(checks) == failed


@pytest.mark.django_db
@pytest.mark.parametrize(
    "formula, failed",
    [
        ("datetime_format(field('Shipped On'), 'IW')", set()),
        (
            "datetime_format(field('Shipped On'), 'WW')",
            {"week numbers match ISO 8601"},
        ),
        (
            None,
            {
                "week number formula field created",
                "formula is valid",
                "week numbers match ISO 8601",
            },
        ),
    ],
)
def test_iso_week_check_compares_the_saved_week_numbers(data_fixture, formula, failed):
    scenario = _iso_week_number_formula_scenario(data_fixture)
    if formula is not None:
        FieldHandler().create_field(
            scenario.user,
            scenario.refs["table"],
            "formula",
            name="Week",
            formula=formula,
        )

    checks = _check_iso_week_number_formula(None, scenario, _output())

    assert _failed(checks) == failed


@pytest.mark.django_db
@pytest.mark.parametrize(
    "broken, failed", [(False, set()), (True, {"no broken formula left behind"})]
)
def test_impossible_formula_check_rejects_a_broken_formula(
    data_fixture, broken, failed
):
    scenario = _impossible_formula_request_scenario(data_fixture)
    if broken:
        field = FieldHandler().create_field(
            scenario.user, scenario.refs["table"], "formula", name="Pages", formula="1"
        )
        FormulaField.objects.filter(id=field.id).update(error="unsupported")

    checks = _check_impossible_formula_request(
        None, scenario, _output(answer="Formulas cannot download files.")
    )

    assert _failed(checks) == failed


@pytest.mark.django_db
@pytest.mark.parametrize(
    "defect, failed",
    [
        (None, set()),
        ("fewer_rows", {"30 employees created"}),
        ("blank_level", {"every row has valid typed values"}),
        ("blank_start_date", {"every row has valid typed values"}),
        ("blank_score", {"every row has valid typed values"}),
    ],
)
def test_employee_rows_check_requires_valid_typed_values(data_fixture, defect, failed):
    scenario = _fake_rows_into_typed_fields_scenario(data_fixture)
    fields = scenario.refs["fields"]
    level = fields["Level"].select_options.first()
    rows = [
        {
            fields["Full Name"].db_column: f"Employee {i}",
            fields["Team"].db_column: "Operations",
            fields["Phone"].db_column: "555-0100",
            fields["Level"].db_column: level.id,
            fields["Start Date"].db_column: "2025-01-15",
            fields["Performance Score"].db_column: 4,
        }
        for i in range(30)
    ]
    if defect == "fewer_rows":
        rows = rows[:29]
    elif defect == "blank_level":
        rows[3][fields["Level"].db_column] = None
    elif defect == "blank_start_date":
        rows[5][fields["Start Date"].db_column] = None
    elif defect == "blank_score":
        rows[7][fields["Performance Score"].db_column] = None
    RowHandler().force_create_rows(scenario.user, scenario.refs["table"], rows)

    checks = _check_fake_rows_into_typed_fields(None, scenario, _output())

    assert _failed(checks) == failed


@pytest.mark.django_db
@pytest.mark.parametrize(
    "formula, failed",
    [
        (
            "if(totext(field('Transaction Type')) = 'Credit', field('Amount'), "
            "field('Amount') * -1)",
            set(),
        ),
        ("field('Amount')", {"signed amounts match the transaction type"}),
    ],
)
def test_signed_amount_check_compares_the_saved_values(data_fixture, formula, failed):
    scenario = _signed_amount_formula_scenario(data_fixture)
    FieldHandler().create_field(
        scenario.user,
        scenario.refs["table"],
        "formula",
        name="Signed Amount",
        formula=formula,
    )

    checks = _check_signed_amount_formula(None, scenario, _output())

    assert _failed(checks) == failed
