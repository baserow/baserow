"""Kuma-dashboard eval dataset: summary and chart widgets on a dashboard."""

from __future__ import annotations

from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.dashboard.tools.widgets import create_widgets, list_widgets
from baserow.core.tools import ToolContext
from baserow.test_utils.fixtures import Fixtures
from baserow_enterprise.assistant.deps import AgentMode
from baserow_enterprise.assistant.evals.harness import tool_called
from baserow_enterprise.assistant.evals.registry import (
    register_case,
    register_scenario,
)
from baserow_enterprise.assistant.evals.types import (
    CheckResult,
    EvalCase,
    EvalRunOutput,
    EvalScenario,
)
from baserow_enterprise.assistant.types import (
    DashboardUIContext,
    UIContext,
    UserUIContext,
    WorkspaceUIContext,
)

PROMPT_ADDS_REVENUE_SUMMARY = (
    "Add a widget to the 'Sales' dashboard with the total revenue: the sum of "
    "Amount in the Orders table."
)
PROMPT_ADDS_CHART_BY_STAGE = (
    "On the 'Sales' dashboard, add a chart of the number of deals per stage from "
    "the Deals table."
)
PROMPT_CHANGES_TO_AVERAGE = (
    "Change the Revenue widget on this dashboard to show the average order amount "
    "instead of the total."
)
PROMPT_READS_WIDGET = "What does the Revenue widget on this dashboard show right now?"
PROMPT_ANSWERS_FROM_CHART = (
    "Make the Deals by stage chart a doughnut, then tell me how many deals are Won."
)


def _dashboard_ui_context(user, workspace, dashboard: Dashboard) -> str:
    return UIContext(
        workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
        dashboard=DashboardUIContext(id=str(dashboard.id), name=dashboard.name),
        user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
    ).format()


def _grant_premium(user) -> None:
    """
    Give the user the premium licence of the premium tests. Charts need it. The
    eval database is disposable and runs with the debug licence key, which that
    licence is signed for, on instance id "1".
    """

    from baserow_premium_tests.fixtures import VALID_100_SEAT_LICENSE_UNTIL_YEAR_2099

    from baserow.core.models import Settings
    from baserow_premium.license.models import License, LicenseUser

    Settings.objects.update(instance_id="1")
    licence, _ = License.objects.get_or_create(
        license=VALID_100_SEAT_LICENSE_UNTIL_YEAR_2099.decode()
    )
    LicenseUser.objects.get_or_create(user=user, license=licence)


def _sales_workspace(fx: Fixtures, with_revenue_widget: bool = False) -> EvalScenario:
    """
    A workspace with an Orders table (Customer, Amount), a Deals table (Name,
    Stage) and an empty Sales dashboard, opened in the UI.
    """

    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace, name="CRM")

    orders = fx.create_database_table(database=database, name="Orders")
    fx.create_text_field(table=orders, name="Customer", primary=True)
    amount = fx.create_number_field(table=orders, name="Amount")
    model = orders.get_model()
    for customer, value in (("Acme", 120), ("Globex", 80), ("Initech", 100)):
        model.objects.create(
            **{
                f"field_{orders.field_set.get(name='Customer').id}": customer,
                f"field_{amount.id}": value,
            }
        )

    deals = fx.create_database_table(database=database, name="Deals")
    fx.create_text_field(table=deals, name="Name", primary=True)
    stage = fx.create_single_select_field(table=deals, name="Stage")
    won = fx.create_select_option(field=stage, value="Won")
    lost = fx.create_select_option(field=stage, value="Lost")
    deal_model = deals.get_model()
    for option in (won, won, lost):
        deal_model.objects.create(**{f"field_{stage.id}_id": option.id})

    dashboard = fx.create_dashboard_application(workspace=workspace, name="Sales")
    fx.create_local_baserow_integration(application=dashboard, authorized_user=user)
    refs = {
        "dashboard": dashboard,
        "orders": orders,
        "amount": amount,
        "deals": deals,
        "stage": stage,
    }
    if with_revenue_widget:
        (widget,) = create_widgets(
            ToolContext(user=user, workspace=workspace),
            dashboard.id,
            [
                {
                    "type": "summary",
                    "title": "Revenue",
                    "table_id": orders.id,
                    "field_id": amount.id,
                    "aggregation_type": "sum",
                }
            ],
        )["created"]
        refs["widget_id"] = widget["id"]

    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=_dashboard_ui_context(user, workspace, dashboard),
        refs=refs,
    )


def _widgets(scenario: EvalScenario) -> list[dict]:
    return list_widgets(
        ToolContext(user=scenario.user, workspace=scenario.workspace),
        scenario.refs["dashboard"].id,
    )["widgets"]


# ---------------------------------------------------------------------------
# Adds a summary widget
# ---------------------------------------------------------------------------


@register_scenario("dashboard-sales")
def _sales_scenario(fx: Fixtures) -> EvalScenario:
    return _sales_workspace(fx)


def _check_adds_revenue_summary(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    widgets = _widgets(scenario)
    matching = [
        w
        for w in widgets
        if w["type"] == "summary"
        and w["field_id"] == scenario.refs["amount"].id
        and w["aggregation_type"] == "sum"
    ]
    return [
        CheckResult(
            "called create_widgets", tool_called(output, "create_widgets") >= 1
        ),
        CheckResult(
            "one summary of sum(Amount) on Sales",
            len(matching) == 1 and len(widgets) == 1,
            hint=f"widgets: {widgets}",
        ),
    ]


register_case(
    EvalCase(
        id="dashboard/adds-revenue-summary",
        dataset="kuma-dashboard",
        prompt=PROMPT_ADDS_REVENUE_SUMMARY,
        scenario="dashboard-sales",
        checks=_check_adds_revenue_summary,
        mode=AgentMode.DASHBOARD,
        max_iters=15,
    )
)

# ---------------------------------------------------------------------------
# Adds a chart grouped by a single select (needs premium)
# ---------------------------------------------------------------------------

COUNT_AGGREGATIONS = {"count", "not_empty_count", "unique_count"}


def _check_adds_chart_by_stage(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    widgets = _widgets(scenario)
    matching = [
        w
        for w in widgets
        if w["type"] in ("chart", "pie_chart")
        and w["table_id"] == scenario.refs["deals"].id
        and w["group_by_field_id"] == scenario.refs["stage"].id
        and len(w["series"]) == 1
        and w["series"][0]["aggregation_type"] in COUNT_AGGREGATIONS
    ]
    return [
        CheckResult(
            "called create_widgets", tool_called(output, "create_widgets") >= 1
        ),
        CheckResult(
            "one chart counting Deals grouped by Stage",
            len(matching) == 1 and len(widgets) == 1,
            hint=f"widgets: {widgets}",
        ),
    ]


@register_scenario("dashboard-sales-premium")
def _sales_premium_scenario(fx: Fixtures) -> EvalScenario:
    scenario = _sales_workspace(fx)
    _grant_premium(scenario.user)
    return scenario


register_case(
    EvalCase(
        id="dashboard/adds-chart-by-stage",
        dataset="kuma-dashboard",
        prompt=PROMPT_ADDS_CHART_BY_STAGE,
        scenario="dashboard-sales-premium",
        checks=_check_adds_chart_by_stage,
        mode=AgentMode.DASHBOARD,
        max_iters=15,
    )
)

# ---------------------------------------------------------------------------
# Changes and reads an existing widget
# ---------------------------------------------------------------------------


@register_scenario("dashboard-sales-with-revenue")
def _sales_with_revenue_scenario(fx: Fixtures) -> EvalScenario:
    return _sales_workspace(fx, with_revenue_widget=True)


def _check_changes_to_average(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    widgets = _widgets(scenario)
    return [
        CheckResult(
            "called update_widgets", tool_called(output, "update_widgets") >= 1
        ),
        CheckResult(
            "the Revenue widget averages Amount, and no widget was added",
            [(w["id"], w["field_id"], w["aggregation_type"]) for w in widgets]
            == [
                (
                    scenario.refs["widget_id"],
                    scenario.refs["amount"].id,
                    "average",
                )
            ],
            hint=f"widgets: {widgets}",
        ),
    ]


register_case(
    EvalCase(
        id="dashboard/changes-to-average",
        dataset="kuma-dashboard",
        prompt=PROMPT_CHANGES_TO_AVERAGE,
        scenario="dashboard-sales-with-revenue",
        checks=_check_changes_to_average,
        mode=AgentMode.DASHBOARD,
        max_iters=15,
    )
)


def _check_reads_widget(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    return [
        CheckResult(
            "called get_widget_data", tool_called(output, "get_widget_data") >= 1
        ),
        CheckResult(
            "answer gives the total of 300",
            "300" in output.answer,
            hint=output.answer[:200],
        ),
        CheckResult(
            "changed nothing",
            tool_called(output, "update_widgets") == 0
            and tool_called(output, "create_widgets") == 0
            and tool_called(output, "delete_widgets") == 0,
        ),
    ]


register_case(
    EvalCase(
        id="dashboard/reads-widget",
        dataset="kuma-dashboard",
        prompt=PROMPT_READS_WIDGET,
        scenario="dashboard-sales-with-revenue",
        checks=_check_reads_widget,
        mode=AgentMode.DASHBOARD,
        max_iters=10,
    )
)


# ---------------------------------------------------------------------------
# Answers a question from a chart that already shows it
# ---------------------------------------------------------------------------


@register_scenario("dashboard-sales-with-stage-chart")
def _sales_with_stage_chart_scenario(fx: Fixtures) -> EvalScenario:
    scenario = _sales_workspace(fx)
    _grant_premium(scenario.user)
    refs = scenario.refs
    (widget,) = create_widgets(
        ToolContext(user=scenario.user, workspace=scenario.workspace),
        refs["dashboard"].id,
        [
            {
                "type": "pie_chart",
                "title": "Deals by stage",
                "table_id": refs["deals"].id,
                "series": [
                    {
                        "field_id": refs["deals"].field_set.get(name="Name").id,
                        "aggregation_type": "count",
                    }
                ],
                "group_by_field_id": refs["stage"].id,
            }
        ],
    )["created"]
    refs["widget_id"] = widget["id"]
    # A view that already filters on Won, like the one the user may keep.
    won_view = fx.create_grid_view(table=refs["deals"], name="Won only")
    fx.create_view_filter(
        view=won_view,
        field=refs["stage"],
        type="single_select_equal",
        value=str(refs["stage"].select_options.get(value="Won").id),
    )
    return scenario


UNREQUESTED_WRITE_TOOLS = (
    "create_widgets",
    "delete_widgets",
    "create_views",
    "create_view_filters",
)


def _check_answers_from_chart(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    (widget,) = _widgets(scenario)
    return [
        CheckResult(
            "the chart is a doughnut",
            widget["chart_type"] == "DOUGHNUT",
            hint=f"widget: {widget}",
        ),
        CheckResult(
            "answer gives 2 Won deals",
            "2" in output.answer,
            hint=output.answer[:200],
        ),
        CheckResult(
            "changed nothing else",
            not any(tool_called(output, name) for name in UNREQUESTED_WRITE_TOOLS),
            hint=f"tool calls: {output.tool_calls}",
        ),
    ]


register_case(
    EvalCase(
        id="dashboard/answers-from-chart",
        dataset="kuma-dashboard",
        prompt=PROMPT_ANSWERS_FROM_CHART,
        scenario="dashboard-sales-with-stage-chart",
        checks=_check_answers_from_chart,
        mode=AgentMode.DASHBOARD,
        max_iters=10,
    )
)
