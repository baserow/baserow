import pytest

from baserow.contrib.dashboard.data_sources.actions import (
    UpdateDashboardDataSourceActionType,
)
from baserow.contrib.dashboard.data_sources.service import DashboardDataSourceService
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowAggregateRowsUserServiceType,
)
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.services.registries import service_type_registry
from baserow.test_utils.helpers import assert_undo_redo_actions_are_valid


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_redo_update_data_source(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    table_2 = data_fixture.create_database_table(database=database)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table_2)
    dashboard = data_fixture.create_dashboard_application(
        workspace=workspace, name="Dashboard 1", description="Description 1", user=user
    )
    widget = WidgetService().create_widget(
        user,
        "summary",
        dashboard.id,
        title="Widget title",
        description="Widget description",
    )
    service_type = service_type_registry.get(
        LocalBaserowAggregateRowsUserServiceType.type
    )
    result = DashboardDataSourceService().update_data_source(
        user,
        widget.data_source.id,
        service_type,
        table_id=table.id,
        field_id=field.id,
        aggregation_type="sum",
    )
    data_source = result.data_source

    # do
    new_data = {
        "table_id": table_2.id,
        "field_id": field_2.id,
        "aggregation_type": "min",
    }
    updated_data_source = action_type_registry.get_by_type(
        UpdateDashboardDataSourceActionType
    ).do(user, data_source.id, service_type, new_data)

    assert updated_data_source.service.table.id == table_2.id
    assert updated_data_source.service.field.id == field_2.id
    assert updated_data_source.service.aggregation_type == "min"

    # undo
    ActionHandler.undo(
        user,
        [ApplicationActionScopeType.value(application_id=dashboard.id)],
        session_id,
    )

    updated_data_source.refresh_from_db()
    assert updated_data_source.service.specific.table.id == table.id
    assert updated_data_source.service.specific.field.id == field.id
    assert updated_data_source.service.specific.aggregation_type == "sum"

    # redo
    actions_redone = ActionHandler.redo(
        user,
        [ApplicationActionScopeType.value(application_id=dashboard.id)],
        session_id,
    )
    assert_undo_redo_actions_are_valid(
        actions_redone, [UpdateDashboardDataSourceActionType]
    )

    updated_data_source.refresh_from_db()
    assert updated_data_source.service.specific.table.id == table_2.id
    assert updated_data_source.service.specific.field.id == field_2.id
    assert updated_data_source.service.specific.aggregation_type == "min"
