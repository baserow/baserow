"""Tests for the widget read tools, shared by MCP and Kuma."""

import pytest

from baserow.contrib.dashboard.tools.widgets import (
    get_widget_data,
    get_widget_in_workspace,
    list_widgets,
)
from baserow.contrib.dashboard.widgets.exceptions import WidgetDoesNotExist
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.core.exceptions import ApplicationDoesNotExist


@pytest.fixture
def summary_widget(data_fixture, dashboard_ctx):
    """A summary widget that sums the Amount field of a table with 2 and 3."""

    ctx, dashboard = dashboard_ctx
    database = data_fixture.create_database_application(workspace=ctx.workspace)
    table = data_fixture.create_database_table(database=database)
    amount = data_fixture.create_number_field(table=table, name="Amount")
    model = table.get_model()
    model.objects.create(**{f"field_{amount.id}": 2})
    model.objects.create(**{f"field_{amount.id}": 3})
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard,
            table=table,
            field=amount,
            aggregation_type="sum",
            integration_args={"authorized_user": ctx.user},
        )
    )
    widget = data_fixture.create_summary_widget(
        dashboard=dashboard, title="Total", data_source=data_source
    )
    return widget, table, amount


@pytest.mark.django_db
def test_list_widgets_describes_summary_config(dashboard_ctx, summary_widget):
    ctx, dashboard = dashboard_ctx
    widget, table, amount = summary_widget

    result = list_widgets(ctx, dashboard.id)

    assert result["dashboard"] == {"id": dashboard.id, "name": "Sales"}
    assert result["widgets"] == [
        {
            "id": widget.id,
            "type": "summary",
            "title": "Total",
            "description": "",
            "data_source_id": widget.data_source_id,
            "table_id": table.id,
            "view_id": None,
            "field_id": amount.id,
            "aggregation_type": "sum",
        }
    ]


@pytest.mark.django_db
def test_list_widgets_hides_foreign_dashboard(data_fixture, dashboard_ctx):
    ctx, _ = dashboard_ctx
    foreign = data_fixture.create_dashboard_application()

    with pytest.raises(ApplicationDoesNotExist):
        list_widgets(ctx, foreign.id)


@pytest.mark.django_db
def test_list_widgets_queries_do_not_grow_with_widgets(
    data_fixture, dashboard_ctx, summary_widget, django_assert_max_num_queries
):
    ctx, dashboard = dashboard_ctx
    list_widgets(ctx, dashboard.id)
    with django_assert_max_num_queries(50) as captured:
        list_widgets(ctx, dashboard.id)
    baseline = len(captured)

    for _ in range(3):
        data_fixture.create_summary_widget(dashboard=dashboard)
    with django_assert_max_num_queries(baseline):
        list_widgets(ctx, dashboard.id)


@pytest.mark.django_db
def test_get_widget_data_returns_summary_result(dashboard_ctx, summary_widget):
    ctx, _ = dashboard_ctx
    widget, _, _ = summary_widget

    assert get_widget_data(ctx, [widget.id]) == {
        "widgets": [
            {"widget_id": widget.id, "configured": True, "data": {"result": "5"}}
        ],
        "errors": [],
    }


@pytest.mark.django_db
def test_get_widget_data_marks_unconfigured_widget(dashboard_ctx, summary_widget):
    ctx, dashboard = dashboard_ctx
    configured, _, _ = summary_widget
    new = WidgetService().create_widget(ctx.user, "summary", dashboard.id, title="New")

    result = get_widget_data(ctx, [new.id, configured.id])

    assert result["errors"] == []
    assert result["widgets"] == [
        {
            "widget_id": new.id,
            "configured": False,
            "data": None,
            "problem": "The field property is missing.",
        },
        {"widget_id": configured.id, "configured": True, "data": {"result": "5"}},
    ]


@pytest.mark.django_db
def test_get_widget_data_hides_widget_of_other_workspace(data_fixture, dashboard_ctx):
    ctx, _ = dashboard_ctx
    foreign = data_fixture.create_summary_widget()

    result = get_widget_data(ctx, [foreign.id, 999999])

    assert result["widgets"] == []
    assert result["errors"] == [
        {"widget_id": foreign.id, "error": "Not found in this workspace."},
        {"widget_id": 999999, "error": "Not found in this workspace."},
    ]


@pytest.mark.django_db
def test_get_widget_in_workspace_hides_trashed_widget(dashboard_ctx, summary_widget):
    ctx, _ = dashboard_ctx
    widget, _, _ = summary_widget
    widget.trashed = True
    widget.save()

    with pytest.raises(WidgetDoesNotExist):
        get_widget_in_workspace(ctx, widget.id)
