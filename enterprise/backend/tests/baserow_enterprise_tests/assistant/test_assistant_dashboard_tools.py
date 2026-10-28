import pytest
from pydantic_ai import ModelRetry

from baserow.contrib.dashboard.widgets.models import Widget
from baserow_enterprise.assistant.assistant import _mode_for_ui_context
from baserow_enterprise.assistant.deps import AgentMode
from baserow_enterprise.assistant.tools.dashboard.tools import (
    create_widgets,
    delete_widgets,
    get_widget_data,
    list_widgets,
    update_widgets,
)
from baserow_enterprise.assistant.types import DashboardNavigationType, UIContext

from .utils import create_fake_tool_helpers, make_test_ctx


@pytest.fixture
def sales(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(
        workspace=workspace, name="Sales"
    )
    data_fixture.create_local_baserow_integration(
        application=dashboard, authorized_user=user
    )
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    amount = data_fixture.create_number_field(table=table, name="Amount")
    model = table.get_model()
    model.objects.create(**{f"field_{amount.id}": 2})
    model.objects.create(**{f"field_{amount.id}": 3})
    return user, workspace, dashboard, table, amount


def _summary(table, amount, aggregation_type="sum"):
    return {
        "type": "summary",
        "title": "Revenue",
        "table_id": table.id,
        "field_id": amount.id,
        "aggregation_type": aggregation_type,
    }


@pytest.mark.django_db
def test_create_widgets_adds_them_and_opens_the_dashboard(sales):
    user, workspace, dashboard, table, amount = sales
    navigations = []
    tool_helpers = create_fake_tool_helpers()
    tool_helpers.navigate_to = navigations.append
    ctx = make_test_ctx(user, workspace, tool_helpers=tool_helpers)

    result = create_widgets(
        ctx, dashboard.id, [_summary(table, amount)], thought="Add revenue"
    )

    assert result["errors"] == []
    assert result["created"][0]["title"] == "Revenue"
    assert navigations == [
        DashboardNavigationType(
            type="dashboard", dashboard_id=dashboard.id, dashboard_name="Sales"
        )
    ]


@pytest.mark.django_db
def test_create_widgets_does_not_navigate_when_nothing_is_created(sales, data_fixture):
    user, workspace, dashboard, table, _ = sales
    navigations = []
    tool_helpers = create_fake_tool_helpers()
    tool_helpers.navigate_to = navigations.append
    ctx = make_test_ctx(user, workspace, tool_helpers=tool_helpers)
    name = table.field_set.get(name="Name")

    result = create_widgets(
        ctx, dashboard.id, [_summary(table, name)], thought="Add revenue"
    )

    assert result["created"] == []
    assert "sum can't be used on field 'Name'" in result["errors"][0]["error"]
    assert navigations == []


@pytest.mark.django_db
def test_create_widgets_rejects_an_empty_payload(sales):
    user, workspace, dashboard, *_ = sales

    with pytest.raises(ModelRetry):
        create_widgets(make_test_ctx(user, workspace), dashboard.id, [], thought="")


@pytest.mark.django_db
def test_read_update_and_delete_widgets_through_the_shared_tools(sales):
    user, workspace, dashboard, table, amount = sales
    ctx = make_test_ctx(user, workspace)
    widget_id = create_widgets(
        ctx, dashboard.id, [_summary(table, amount)], thought=""
    )["created"][0]["id"]

    listed = list_widgets(ctx, dashboard.id, thought="")
    assert [w["id"] for w in listed["widgets"]] == [widget_id]
    assert get_widget_data(ctx, [widget_id], thought="")["widgets"][0]["data"] == {
        "result": "5"
    }

    updated = update_widgets(
        ctx, [{"widget_id": widget_id, "aggregation_type": "max"}], thought=""
    )
    assert updated["updated"][0]["aggregation_type"] == "max"
    assert get_widget_data(ctx, [widget_id], thought="")["widgets"][0]["data"] == {
        "result": "3"
    }

    assert delete_widgets(ctx, [widget_id], thought="")["deleted"] == [widget_id]
    assert Widget.objects_and_trash.get(id=widget_id).trashed


@pytest.mark.django_db
def test_an_open_dashboard_starts_in_dashboard_mode(sales):
    user, workspace, dashboard, *_ = sales

    ui_context = UIContext(
        workspace={"id": workspace.id, "name": workspace.name},
        dashboard={"id": str(dashboard.id), "name": dashboard.name},
        user={"id": user.id, "name": user.first_name, "email": user.email},
    )

    assert _mode_for_ui_context(ui_context) == AgentMode.DASHBOARD


@pytest.mark.parametrize(
    "key,producer",
    [
        ("dashboard_id", "list_builders"),
        ("widget_id", "list_widgets"),
        ("widget_ids", "list_widgets"),
    ],
)
def test_dashboard_ids_name_the_tool_that_lists_them(key, producer):
    from baserow_enterprise.assistant.tools.toolset import _id_producer

    assert _id_producer(key.removesuffix("s")) == producer
