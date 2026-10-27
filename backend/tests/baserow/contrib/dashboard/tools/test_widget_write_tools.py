"""Tests for the widget write tools, shared by MCP and Kuma."""

import pytest

from baserow.contrib.dashboard.data_sources.actions import (
    UpdateDashboardDataSourceActionType,
)
from baserow.contrib.dashboard.tools.types import WidgetUpdate
from baserow.contrib.dashboard.tools.widgets import (
    create_widgets,
    delete_widgets,
    get_widget_data,
    list_widgets,
    update_widgets,
)
from baserow.contrib.dashboard.widgets.actions import (
    CreateWidgetActionType,
    DeleteWidgetActionType,
    UpdateWidgetActionType,
)
from baserow.contrib.dashboard.widgets.models import Widget
from baserow.core.action.models import Action

NOT_FOUND = "Not found in this workspace."


@pytest.fixture
def sales_table(data_fixture, dashboard_ctx):
    """A table in the workspace with a Name text field and an Amount number field."""

    ctx, _ = dashboard_ctx
    database = data_fixture.create_database_application(workspace=ctx.workspace)
    table = data_fixture.create_database_table(database=database)
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)
    amount = data_fixture.create_number_field(table=table, name="Amount")
    model = table.get_model()
    model.objects.create(**{f"field_{amount.id}": 2})
    model.objects.create(**{f"field_{amount.id}": 3})
    return table, name, amount


def _summary(table, field, aggregation_type="sum", **kwargs):
    return {
        "type": "summary",
        "title": "Total",
        "table_id": table.id,
        "field_id": field.id,
        "aggregation_type": aggregation_type,
        **kwargs,
    }


def _action_types(user):
    return list(
        Action.objects.filter(user=user).order_by("id").values_list("type", flat=True)
    )


@pytest.mark.django_db
def test_create_summary_widget_stores_config_and_two_undo_actions(
    dashboard_ctx, sales_table
):
    ctx, dashboard = dashboard_ctx
    table, _, amount = sales_table

    result = create_widgets(ctx, dashboard.id, [_summary(table, amount)])

    assert result["errors"] == []
    (created,) = result["created"]
    assert created["type"] == "summary"
    assert created["title"] == "Total"
    assert created["table_id"] == table.id
    assert created["field_id"] == amount.id
    assert created["aggregation_type"] == "sum"
    data = get_widget_data(ctx, [created["id"]])["widgets"][0]
    assert data == {
        "widget_id": created["id"],
        "configured": True,
        "data": {"result": "5"},
    }
    assert _action_types(ctx.user) == [
        CreateWidgetActionType.type,
        UpdateDashboardDataSourceActionType.type,
    ]


@pytest.mark.django_db
def test_create_widget_with_view_of_the_table(data_fixture, dashboard_ctx, sales_table):
    ctx, dashboard = dashboard_ctx
    table, _, amount = sales_table
    view = data_fixture.create_grid_view(table=table)

    result = create_widgets(
        ctx, dashboard.id, [_summary(table, amount, view_id=view.id)]
    )

    assert result["errors"] == []
    assert result["created"][0]["view_id"] == view.id


@pytest.mark.django_db
def test_create_widget_reports_aggregation_that_does_not_fit_field(
    dashboard_ctx, sales_table
):
    ctx, dashboard = dashboard_ctx
    table, name, _ = sales_table

    result = create_widgets(ctx, dashboard.id, [_summary(table, name, "sum")])

    assert result["created"] == []
    (error,) = result["errors"]
    assert error["index"] == 0
    assert "sum can't be used on field 'Name'" in error["error"]
    assert "empty_count" in error["error"]
    assert "distribution" not in error["error"]
    assert Widget.objects.filter(dashboard=dashboard).count() == 0


@pytest.mark.django_db
def test_create_widget_reports_unknown_aggregation(dashboard_ctx, sales_table):
    ctx, dashboard = dashboard_ctx
    table, _, amount = sales_table

    result = create_widgets(ctx, dashboard.id, [_summary(table, amount, "total")])

    assert "total can't be used on field 'Amount'" in result["errors"][0]["error"]
    assert Widget.objects.filter(dashboard=dashboard).count() == 0


@pytest.mark.django_db
def test_create_widget_rejects_field_of_other_table(
    data_fixture, dashboard_ctx, sales_table
):
    ctx, dashboard = dashboard_ctx
    table, _, _ = sales_table
    other = data_fixture.create_database_table(database=table.database)
    other_amount = data_fixture.create_number_field(table=other)

    result = create_widgets(ctx, dashboard.id, [_summary(table, other_amount)])

    assert result["created"] == []
    assert result["errors"] == [{"index": 0, "error": NOT_FOUND}]
    assert Widget.objects.filter(dashboard=dashboard).count() == 0


@pytest.mark.django_db
def test_create_widget_rejects_table_of_other_workspace(data_fixture, dashboard_ctx):
    ctx, dashboard = dashboard_ctx
    foreign_table = data_fixture.create_database_table()
    foreign_field = data_fixture.create_number_field(table=foreign_table)

    result = create_widgets(ctx, dashboard.id, [_summary(foreign_table, foreign_field)])

    assert result["errors"] == [{"index": 0, "error": NOT_FOUND}]
    assert Widget.objects.filter(dashboard=dashboard).count() == 0


@pytest.mark.django_db
def test_create_widget_rejects_view_of_other_table(
    data_fixture, dashboard_ctx, sales_table
):
    ctx, dashboard = dashboard_ctx
    table, _, amount = sales_table
    other = data_fixture.create_database_table(database=table.database)
    other_view = data_fixture.create_grid_view(table=other)

    result = create_widgets(
        ctx, dashboard.id, [_summary(table, amount, view_id=other_view.id)]
    )

    assert result["errors"] == [{"index": 0, "error": NOT_FOUND}]
    assert Widget.objects.filter(dashboard=dashboard).count() == 0
    assert Action.objects.filter(user=ctx.user).count() == 0


@pytest.mark.django_db
def test_create_widgets_keeps_good_items_when_one_fails(dashboard_ctx, sales_table):
    ctx, dashboard = dashboard_ctx
    table, name, amount = sales_table

    result = create_widgets(
        ctx, dashboard.id, [_summary(table, amount), _summary(table, name, "sum")]
    )

    assert len(result["created"]) == 1
    assert [e["index"] for e in result["errors"]] == [1]
    assert Widget.objects.filter(dashboard=dashboard).count() == 1


@pytest.mark.django_db
def test_create_widgets_in_foreign_dashboard_is_not_found(data_fixture, dashboard_ctx):
    from baserow.core.exceptions import ApplicationDoesNotExist

    ctx, _ = dashboard_ctx
    foreign = data_fixture.create_dashboard_application()

    with pytest.raises(ApplicationDoesNotExist):
        create_widgets(ctx, foreign.id, [])


@pytest.mark.django_db
def test_update_widget_changes_aggregation_only(dashboard_ctx, sales_table):
    ctx, dashboard = dashboard_ctx
    table, _, amount = sales_table
    widget_id = create_widgets(ctx, dashboard.id, [_summary(table, amount)])["created"][
        0
    ]["id"]
    Action.objects.all().delete()

    result = update_widgets(
        ctx, [WidgetUpdate(widget_id=widget_id, aggregation_type="max")]
    )

    assert result["errors"] == []
    (updated,) = result["updated"]
    assert updated["title"] == "Total"
    assert updated["aggregation_type"] == "max"
    assert updated["field_id"] == amount.id
    assert _action_types(ctx.user) == [UpdateDashboardDataSourceActionType.type]


@pytest.mark.django_db
def test_update_widget_changes_title_only(dashboard_ctx, sales_table):
    ctx, dashboard = dashboard_ctx
    table, _, amount = sales_table
    widget_id = create_widgets(ctx, dashboard.id, [_summary(table, amount)])["created"][
        0
    ]["id"]
    Action.objects.all().delete()

    result = update_widgets(ctx, [{"widget_id": widget_id, "title": "Revenue"}])

    assert result["updated"][0]["title"] == "Revenue"
    assert _action_types(ctx.user) == [UpdateWidgetActionType.type]


@pytest.mark.django_db
def test_update_widget_with_no_changes_is_not_listed(dashboard_ctx, sales_table):
    ctx, dashboard = dashboard_ctx
    table, _, amount = sales_table
    widget_id = create_widgets(ctx, dashboard.id, [_summary(table, amount)])["created"][
        0
    ]["id"]
    Action.objects.all().delete()

    result = update_widgets(
        ctx,
        [{"widget_id": widget_id, "title": "Total", "aggregation_type": "sum"}],
    )

    assert result == {"updated": [], "errors": []}
    assert Action.objects.count() == 0


@pytest.mark.django_db
def test_update_widget_reports_aggregation_that_does_not_fit(
    dashboard_ctx, sales_table
):
    ctx, dashboard = dashboard_ctx
    table, name, amount = sales_table
    widget_id = create_widgets(ctx, dashboard.id, [_summary(table, amount)])["created"][
        0
    ]["id"]

    result = update_widgets(
        ctx, [{"widget_id": widget_id, "field_id": name.id, "title": "New"}]
    )

    assert result["updated"] == []
    assert result["errors"][0]["widget_id"] == widget_id
    assert "sum can't be used on field 'Name'" in result["errors"][0]["error"]
    # Nothing of the item is kept, the title neither.
    assert list_widgets(ctx, dashboard.id)["widgets"][0]["title"] == "Total"


@pytest.mark.django_db
def test_update_summary_widget_rejects_chart_values(dashboard_ctx, sales_table):
    ctx, dashboard = dashboard_ctx
    table, _, amount = sales_table
    widget_id = create_widgets(ctx, dashboard.id, [_summary(table, amount)])["created"][
        0
    ]["id"]

    result = update_widgets(ctx, [{"widget_id": widget_id, "chart_type": "LINE"}])

    assert result["updated"] == []
    assert "chart_type" in result["errors"][0]["error"]


@pytest.mark.django_db
def test_update_foreign_widget_is_not_found(data_fixture, dashboard_ctx):
    ctx, _ = dashboard_ctx
    foreign = data_fixture.create_summary_widget()

    result = update_widgets(ctx, [{"widget_id": foreign.id, "title": "Hacked"}])

    assert result["errors"] == [
        {"index": 0, "widget_id": foreign.id, "error": NOT_FOUND}
    ]
    foreign.refresh_from_db()
    assert foreign.title != "Hacked"


@pytest.mark.django_db
def test_delete_widgets_trashes_and_hides_foreign(
    data_fixture, dashboard_ctx, sales_table
):
    ctx, dashboard = dashboard_ctx
    table, _, amount = sales_table
    widget_id = create_widgets(ctx, dashboard.id, [_summary(table, amount)])["created"][
        0
    ]["id"]
    foreign = data_fixture.create_summary_widget()

    result = delete_widgets(ctx, [widget_id, foreign.id, 999999])

    assert result["deleted"] == [widget_id]
    assert [e["widget_id"] for e in result["errors"]] == [foreign.id, 999999]
    assert {e["error"] for e in result["errors"]} == {NOT_FOUND}
    assert Widget.objects_and_trash.get(id=widget_id).trashed
    assert not Widget.objects_and_trash.get(id=foreign.id).trashed
    assert DeleteWidgetActionType.type in _action_types(ctx.user)

    again = delete_widgets(ctx, [widget_id])
    assert again["deleted"] == []
    assert again["errors"] == [{"widget_id": widget_id, "error": NOT_FOUND}]
