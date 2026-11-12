from copy import deepcopy

from django.http import HttpRequest
from django.urls import reverse

import pytest

from baserow.contrib.dashboard.data_sources.actions import (
    UpdateDashboardDataSourceActionType,
)
from baserow.contrib.dashboard.data_sources.dispatch_context import (
    DashboardDispatchContext,
)
from baserow.contrib.dashboard.data_sources.handler import DashboardDataSourceHandler
from baserow.contrib.dashboard.data_sources.service import DashboardDataSourceService
from baserow.contrib.dashboard.widgets.models import TextFilterWidget
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.action.handler import ActionHandler
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.formula import BaserowFormulaObject


@pytest.fixture
def table_change(data_fixture):
    user, token = data_fixture.create_user_and_token(session_id="table-change")
    dashboard = data_fixture.create_dashboard_application(user=user)
    database = data_fixture.create_database_application(workspace=dashboard.workspace)
    first = data_fixture.create_database_table(database=database)
    second = data_fixture.create_database_table(database=database)
    field = data_fixture.create_number_field(table=first)
    second_field = data_fixture.create_number_field(table=second)
    RowHandler().create_rows(
        user, first, [{field.db_column: 10}, {field.db_column: 20}]
    )
    RowHandler().create_rows(user, second, [{second_field.db_column: 40}])
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, authorized_user=user
    )
    source = data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
        dashboard=dashboard,
        service=data_fixture.create_local_baserow_aggregate_rows_service(
            integration=integration, table=first, field=field, aggregation_type="sum"
        ),
    )
    target = data_fixture.create_summary_widget(dashboard=dashboard, data_source=source)
    other = data_fixture.create_summary_widget(dashboard=dashboard)
    condition = {
        "field": field.id,
        "type": "equal",
        "value": BaserowFormulaObject.create("10", mode="raw"),
    }
    group = {"filter_type": "AND", "filter_groups": [], "filters": [condition]}
    owner = TextFilterWidget.objects.create(
        dashboard=dashboard,
        title="Country",
        default_value="France",
        target_filters=[
            {
                "target_widget_id": target.id,
                "enabled": False,
                "group": deepcopy(group),
                "empty_behavior": "apply_alternative",
                "alternative_group": deepcopy(group),
            },
            {
                "target_widget_id": other.id,
                "group": deepcopy(group),
                "empty_behavior": "apply_nothing",
            },
        ],
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=source.service.specific,
        field=field,
        type="equal",
        value=BaserowFormulaObject.create("10", mode="raw"),
    )
    return user, token, dashboard, source, owner, second, second_field


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_table_change_resets_and_restores_all_conditions(table_change):
    user, _, dashboard, source, owner, table, field = table_change
    before = deepcopy(owner.target_filters)
    service_type = source.service.get_type()
    UpdateDashboardDataSourceActionType.do(
        user, source.id, service_type, {"table_id": table.id, "field_id": field.id}
    )
    owner.refresh_from_db()
    reset = deepcopy(owner.target_filters)
    assert reset[0] == {
        "target_widget_id": before[0]["target_widget_id"],
        "enabled": False,
        "group": {"filter_type": "AND", "filters": [], "filter_groups": []},
        "empty_behavior": "apply_nothing",
    }
    assert reset[1] == before[1]
    assert owner.default_value == "France"
    source.refresh_from_db()
    assert not source.service.specific.service_filters.exists()
    assert (
        DashboardDataSourceHandler().dispatch_data_source(
            source, DashboardDispatchContext(HttpRequest(), dashboard=dashboard)
        )["result"]
        == "40"
    )
    scopes = [ApplicationActionScopeType.value(dashboard.id)]
    for operation, links, expected in [
        (ActionHandler.undo, before, "10"),
        (ActionHandler.redo, reset, "40"),
    ]:
        actions = operation(user, scopes, "table-change")
        assert actions and not actions[0].error
        owner.refresh_from_db()
        source.refresh_from_db()
        assert owner.target_filters == links
        assert (
            DashboardDataSourceHandler().dispatch_data_source(
                source, DashboardDispatchContext(HttpRequest(), dashboard=dashboard)
            )["result"]
            == expected
        )


@pytest.mark.django_db
def test_other_source_changes_keep_filter_links(table_change):
    user, _, _, source, owner, _, _ = table_change
    before = deepcopy(owner.target_filters)
    DashboardDataSourceService().update_data_source(
        user, source.id, source.service.get_type(), aggregation_type="max"
    )
    owner.refresh_from_db()
    assert owner.target_filters == before


@pytest.mark.django_db
def test_failed_table_change_leaves_conditions_untouched(api_client, table_change):
    _, token, _, source, owner, table, _ = table_change
    before = deepcopy(owner.target_filters)
    response = api_client.patch(
        reverse(
            "api:dashboard:data_sources:item", kwargs={"data_source_id": source.id}
        ),
        {"table_id": 999999999},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400
    owner.refresh_from_db()
    assert owner.target_filters == before
    assert source.service.specific.service_filters.count() == 1


@pytest.mark.django_db
def test_reset_failure_rolls_back_table_and_conditions(monkeypatch, table_change):
    from baserow.contrib.dashboard.widgets.mixins import DisplayWidgetTypeMixin

    user, _, _, source, owner, table, field = table_change
    before = deepcopy(owner.target_filters)
    original_table_id = source.service.specific.table_id
    reset = DisplayWidgetTypeMixin.after_update

    def fail_after_reset(self, updated_widget, **kwargs):
        reset(self, updated_widget, **kwargs)
        raise RuntimeError("Reset failed")

    monkeypatch.setattr(DisplayWidgetTypeMixin, "after_update", fail_after_reset)
    with pytest.raises(RuntimeError, match="Reset failed"):
        DashboardDataSourceService().update_data_source(
            user,
            source.id,
            source.service.get_type(),
            table_id=table.id,
            field_id=field.id,
        )
    source.refresh_from_db()
    owner.refresh_from_db()
    assert source.service.specific.table_id == original_table_id
    assert source.service.specific.service_filters.count() == 1
    assert owner.target_filters == before


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_shared_source_resets_and_restores_each_display(table_change, data_fixture):
    """Each display hook preserves its own undo links without duplicate notifications."""
    user, _, dashboard, source, owner, table, field = table_change
    target = data_fixture.create_summary_widget(dashboard=dashboard, data_source=source)
    extra = deepcopy(owner.target_filters[0])
    extra["target_widget_id"] = target.id
    owner.target_filters.append(extra)
    owner.save()
    before = deepcopy(owner.target_filters)

    UpdateDashboardDataSourceActionType.do(
        user,
        source.id,
        source.service.get_type(),
        {"table_id": table.id, "field_id": field.id},
    )
    owner.refresh_from_db()
    assert owner.target_filters[1] == before[1]
    for index in (0, 2):
        assert owner.target_filters[index]["group"]["filters"] == []
        assert "alternative_group" not in owner.target_filters[index]

    actions = ActionHandler.undo(
        user, [ApplicationActionScopeType.value(dashboard.id)], "table-change"
    )
    assert actions and not actions[0].error
    owner.refresh_from_db()
    assert owner.target_filters == before
