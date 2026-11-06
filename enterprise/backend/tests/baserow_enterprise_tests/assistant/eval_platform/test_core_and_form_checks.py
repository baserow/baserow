"""Eval checks that must fail on an end state that only looks right."""

import pytest

from baserow_enterprise.assistant.evals.datasets.builder import (
    _check_creates_contact_form,
    _creates_contact_form_scenario,
)
from baserow_enterprise.assistant.evals.registry import get_case, get_scenario, load_all
from baserow_enterprise.assistant.evals.scenarios import make_fixtures
from baserow_enterprise.assistant.evals.types import EvalRunOutput


def _output(*tool_calls, answer="Done"):
    return EvalRunOutput(
        answer=answer,
        messages=[],
        tool_calls=list(tool_calls),
        tool_error_count=0,
        tool_error_hint="",
        sources=[],
        request_count=1,
        duration_s=0.0,
    )


def _run(case_id, output, prepare=None):
    load_all()
    case = get_case(case_id)
    scenario = get_scenario(case.scenario)(make_fixtures())
    if prepare:
        prepare(scenario)
    return {check.name: check.passed for check in case.checks(case, scenario, output)}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name,extra_automation,passes",
    [
        ("Sales Overview", False, True),
        ("Sales Mistake", False, False),
        ("Sales Overview", True, False),
    ],
)
def test_creates_dashboard_check_wants_the_name_and_nothing_else(
    data_fixture, name, extra_automation, passes
):
    def prepare(scenario):
        data_fixture.create_dashboard_application(
            workspace=scenario.workspace, name=name
        )
        if extra_automation:
            data_fixture.create_automation_application(workspace=scenario.workspace)

    checks = _run("core/creates-dashboard", _output("create_dashboard"), prepare)

    assert all(checks.values()) is passes


@pytest.mark.django_db
@pytest.mark.parametrize(
    "answer,passes",
    [
        ("The Invoices table is in the Sales database.", True),
        (
            "I only found Operations > Tasks, there are no invoices. "
            "Should I create an Invoices table?",
            False,
        ),
        ("I couldn't find an invoices table in Sales.", False),
    ],
)
def test_search_finds_table_check_rejects_a_denial(answer, passes):
    checks = _run("core/search-finds-table", _output("search_workspace", answer=answer))

    assert all(checks.values()) is passes


def _contact_form(data_fixture, scenario, email_reads_name):
    page = data_fixture.create_builder_page(
        builder=scenario.refs["builder"], name="Contact", path="/contact"
    )
    form = data_fixture.create_builder_form_container_element(page=page)
    name_input = data_fixture.create_builder_input_text_element(
        page=page, parent_element=form, label="'Name'"
    )
    email_input = data_fixture.create_builder_input_text_element(
        page=page, parent_element=form, label="'Email'", validation_type="email"
    )
    service = data_fixture.create_local_baserow_upsert_row_service(
        table=scenario.refs["table"]
    )
    email_source = name_input if email_reads_name else email_input
    service.field_mappings.create(
        field=scenario.refs["name_field"], value=f"get('form_data.{name_input.id}')"
    )
    service.field_mappings.create(
        field=scenario.refs["email_field"],
        value=f"get('form_data.{email_source.id}')",
    )
    data_fixture.create_local_baserow_create_row_workflow_action(
        page=page, service=service, element=form, event="submit"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("email_reads_name,passes", [(False, True), (True, False)])
def test_creates_contact_form_check_wants_each_field_from_its_input(
    data_fixture, email_reads_name, passes
):
    scenario = _creates_contact_form_scenario(make_fixtures())
    _contact_form(data_fixture, scenario, email_reads_name)

    checks = _check_creates_contact_form(None, scenario, _output())

    assert all(c.passed for c in checks) is passes
