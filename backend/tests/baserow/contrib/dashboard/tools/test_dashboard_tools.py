"""Tests for the dashboard tools, shared by MCP and Kuma."""

from django.core.exceptions import ValidationError as DjangoValidationError

import pydantic
import pytest
from pydantic import TypeAdapter

from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.dashboard.tools.dashboards import (
    create_dashboards,
    get_dashboard_in_workspace,
    list_dashboards,
)
from baserow.contrib.dashboard.tools.types import WidgetCreate
from baserow.core.action.models import Action
from baserow.core.actions import CreateApplicationActionType
from baserow.core.exceptions import ApplicationDoesNotExist


@pytest.mark.django_db
def test_list_dashboards_only_lists_dashboards_of_the_workspace(
    data_fixture, dashboard_ctx
):
    ctx, dashboard = dashboard_ctx
    data_fixture.create_database_application(workspace=ctx.workspace)
    data_fixture.create_dashboard_application()
    data_fixture.create_summary_widget(dashboard=dashboard)
    trashed = data_fixture.create_summary_widget(dashboard=dashboard)
    trashed.trashed = True
    trashed.save()

    assert list_dashboards(ctx) == {
        "dashboards": [{"id": dashboard.id, "name": "Sales", "widget_count": 1}]
    }


@pytest.mark.django_db
def test_list_dashboards_counts_widgets_in_one_query(
    data_fixture, dashboard_ctx, django_assert_max_num_queries
):
    ctx, dashboard = dashboard_ctx
    for _ in range(3):
        other = data_fixture.create_dashboard_application(workspace=ctx.workspace)
        data_fixture.create_summary_widget(dashboard=other)
    list_dashboards(ctx)

    with django_assert_max_num_queries(5) as captured:
        list_dashboards(ctx)
    baseline = len(captured)
    data_fixture.create_dashboard_application(workspace=ctx.workspace)
    with django_assert_max_num_queries(baseline):
        list_dashboards(ctx)


@pytest.mark.django_db
def test_get_dashboard_in_workspace_hides_foreign_dashboard(
    data_fixture, dashboard_ctx
):
    ctx, dashboard = dashboard_ctx
    foreign = data_fixture.create_dashboard_application()

    assert get_dashboard_in_workspace(ctx, dashboard.id).id == dashboard.id
    with pytest.raises(ApplicationDoesNotExist):
        get_dashboard_in_workspace(ctx, foreign.id)


@pytest.mark.django_db
def test_get_dashboard_in_workspace_hides_other_application_types(
    data_fixture, dashboard_ctx
):
    ctx, _ = dashboard_ctx
    database = data_fixture.create_database_application(workspace=ctx.workspace)

    with pytest.raises(ApplicationDoesNotExist):
        get_dashboard_in_workspace(ctx, database.id)


@pytest.mark.django_db
def test_create_dashboards_registers_undoable_action(dashboard_ctx):
    ctx, _ = dashboard_ctx

    result = create_dashboards(ctx, ["Ops"])

    (created,) = result["created"]
    assert created["name"] == "Ops"
    assert Dashboard.objects.get(id=created["id"]).workspace_id == ctx.workspace.id
    assert (
        Action.objects.filter(
            user=ctx.user, type=CreateApplicationActionType.type
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_create_dashboards_rejects_empty_list(dashboard_ctx):
    ctx, _ = dashboard_ctx

    with pytest.raises(DjangoValidationError):
        create_dashboards(ctx, [])


def test_chart_widget_create_rejects_empty_series():
    with pytest.raises(pydantic.ValidationError):
        TypeAdapter(WidgetCreate).validate_python(
            {"type": "chart", "title": "T", "table_id": 1, "series": []}
        )


def test_widget_create_picks_the_model_by_type():
    adapter = TypeAdapter(WidgetCreate)
    summary = adapter.validate_python(
        {
            "type": "summary",
            "title": "Total",
            "table_id": 1,
            "field_id": 2,
            "aggregation_type": "sum",
        }
    )
    chart = adapter.validate_python(
        {
            "type": "pie_chart",
            "title": "Split",
            "table_id": 1,
            "series": [{"field_id": 2, "aggregation_type": "sum"}],
        }
    )
    assert summary.field_id == 2
    assert chart.series[0].aggregation_type == "sum"
    assert chart.group_by_field_id is None
