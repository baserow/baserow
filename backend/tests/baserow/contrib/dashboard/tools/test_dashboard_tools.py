"""Tests for the dashboard tools, shared by MCP and Kuma."""

import pytest

from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.dashboard.tools.dashboards import (
    create_dashboard,
    get_dashboard_in_workspace,
    list_dashboards,
    update_dashboard,
)
from baserow.core.action.models import Action
from baserow.core.actions import CreateApplicationActionType
from baserow.core.exceptions import ApplicationDoesNotExist, UserNotInWorkspace
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.tools import ToolContext


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
def test_create_dashboard_registers_undoable_action(dashboard_ctx):
    ctx, _ = dashboard_ctx

    result = create_dashboard(ctx, "Ops")

    created = result["created_dashboard"]
    assert created["name"] == "Ops"
    assert Dashboard.objects.get(id=created["id"]).workspace_id == ctx.workspace.id
    assert (
        Action.objects.filter(
            user=ctx.user, type=CreateApplicationActionType.type
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_created_dashboard_can_show_widget_data(dashboard_ctx, data_fixture):
    from baserow.contrib.dashboard.tools.widgets import (
        create_widgets,
        get_widget_data,
    )

    ctx, _ = dashboard_ctx
    database = data_fixture.create_database_application(workspace=ctx.workspace)
    table = data_fixture.create_database_table(database=database)
    amount = data_fixture.create_number_field(table=table, name="Amount")
    table.get_model().objects.create(**{f"field_{amount.id}": 4})

    dashboard_id = create_dashboard(ctx, "Ops")["created_dashboard"]["id"]
    widget = create_widgets(
        ctx,
        dashboard_id,
        [
            {
                "type": "summary",
                "title": "Total",
                "table_id": table.id,
                "field_id": amount.id,
                "aggregation_type": "sum",
            }
        ],
    )["created"][0]

    assert get_widget_data(ctx, [widget["id"]])["widgets"] == [
        {"widget_id": widget["id"], "configured": True, "data": {"result": "4"}}
    ]


@pytest.mark.django_db
def test_create_dashboard_keeps_nothing_when_denied(data_fixture):
    ctx = ToolContext(
        user=data_fixture.create_user(), workspace=data_fixture.create_workspace()
    )

    with pytest.raises(UserNotInWorkspace):
        create_dashboard(ctx, "Ops")
    assert not Dashboard.objects.exists()


@pytest.mark.django_db
def test_create_dashboard_keeps_nothing_when_its_integration_fails(
    dashboard_ctx, monkeypatch
):
    ctx, _ = dashboard_ctx

    def fail(*args, **kwargs):
        raise RuntimeError("write failed")

    monkeypatch.setattr(IntegrationHandler, "create_integration", fail)

    with pytest.raises(RuntimeError):
        create_dashboard(ctx, "Ops")
    assert not Dashboard.objects.filter(name="Ops").exists()


@pytest.mark.django_db
def test_update_dashboard_renames_it(dashboard_ctx, data_fixture):
    ctx, _ = dashboard_ctx
    dashboard = data_fixture.create_dashboard_application(
        workspace=ctx.workspace, name="Old"
    )

    result = update_dashboard(ctx, dashboard.id, "New")

    assert result == {
        "updated_dashboard": {"id": dashboard.id, "name": "New"},
        "changed": True,
    }
    dashboard.refresh_from_db()
    assert dashboard.name == "New"


@pytest.mark.django_db
def test_update_dashboard_refuses_another_application_type(dashboard_ctx, data_fixture):
    ctx, _ = dashboard_ctx
    database = data_fixture.create_database_application(
        workspace=ctx.workspace, name="Sales"
    )

    with pytest.raises(ApplicationDoesNotExist):
        update_dashboard(ctx, database.id, "New")
    database.refresh_from_db()
    assert database.name == "Sales"
