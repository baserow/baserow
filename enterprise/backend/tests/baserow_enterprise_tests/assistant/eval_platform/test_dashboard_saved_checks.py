"""The dashboard eval checks pass on the expected end state and fail without it."""

from django.test.utils import override_settings

import pytest

from baserow.contrib.dashboard.tools.widgets import create_widgets, update_widgets
from baserow.core.tools import ToolContext
from baserow_enterprise.assistant.evals.registry import (
    get_case,
    get_scenario,
    load_all,
)
from baserow_enterprise.assistant.evals.scenarios import make_fixtures
from baserow_enterprise.assistant.evals.types import EvalRunOutput


def _output(*tool_calls, answer=""):
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
        prepare(ToolContext(user=scenario.user, workspace=scenario.workspace), scenario)
    return {check.name: check.passed for check in case.checks(case, scenario, output)}


@pytest.mark.django_db
def test_adds_revenue_summary_check():
    def add(ctx, scenario):
        create_widgets(
            ctx,
            scenario.refs["dashboard"].id,
            [
                {
                    "type": "summary",
                    "title": "Revenue",
                    "table_id": scenario.refs["orders"].id,
                    "field_id": scenario.refs["amount"].id,
                    "aggregation_type": "sum",
                }
            ],
        )

    output = _output("create_widgets")
    assert all(_run("dashboard/adds-revenue-summary", output, add).values())
    assert not all(_run("dashboard/adds-revenue-summary", output).values())


@pytest.mark.django_db
def test_changes_to_average_check():
    def change(ctx, scenario):
        update_widgets(
            ctx,
            [{"widget_id": scenario.refs["widget_id"], "aggregation_type": "average"}],
        )

    output = _output("update_widgets")
    assert all(_run("dashboard/changes-to-average", output, change).values())
    assert not all(_run("dashboard/changes-to-average", output).values())


@pytest.mark.django_db
def test_reads_widget_check():
    case_id = "dashboard/reads-widget"
    assert all(
        _run(case_id, _output("get_widget_data", answer="It shows 300.")).values()
    )
    assert not all(
        _run(case_id, _output("get_widget_data", answer="It shows 120.")).values()
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_answers_from_chart_check_fails_on_an_added_widget_or_a_stray_2():
    def change(ctx, scenario):
        update_widgets(
            ctx, [{"widget_id": scenario.refs["widget_id"], "chart_type": "DOUGHNUT"}]
        )

    def change_and_add(ctx, scenario):
        change(ctx, scenario)
        create_widgets(
            ctx,
            scenario.refs["dashboard"].id,
            [
                {
                    "type": "summary",
                    "title": "Won",
                    "table_id": scenario.refs["deals"].id,
                    "field_id": scenario.refs["deals"].field_set.get(name="Name").id,
                    "aggregation_type": "not_empty_count",
                }
            ],
        )

    case_id = "dashboard/answers-from-chart"
    good = _output("update_widgets", "get_widget_data", answer="2 deals are Won.")
    assert all(_run(case_id, good, change).values())
    assert not all(_run(case_id, good, change_and_add).values())
    stray = _output("update_widgets", answer="3 deals as of 2026-10-28.")
    assert not all(_run(case_id, stray, change).values())
