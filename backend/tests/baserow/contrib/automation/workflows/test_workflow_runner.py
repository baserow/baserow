import pytest

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.nodes.node_types import (
    LocalBaserowCreateRowNodeType,
    LocalBaserowRowsCreatedNodeTriggerType,
)
from baserow.contrib.automation.workflows.runner import AutomationWorkflowRunner


@pytest.mark.django_db
def test_run_workflow(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = data_fixture.create_local_baserow_integration(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    trigger_table = data_fixture.create_database_table(database=database)
    action_table = data_fixture.create_database_table(database=database)
    action_table_field = data_fixture.create_text_field(table=action_table)
    workflow = data_fixture.create_automation_workflow(user=user)
    data_fixture.create_automation_node(
        workflow=workflow,
        node=LocalBaserowRowsCreatedNodeTriggerType.type,
        service=data_fixture.create_local_baserow_rows_created_service(
            table=trigger_table,
            integration=integration,
        ),
    )
    action_node_service = data_fixture.create_local_baserow_upsert_row_service(
        table=action_table,
        integration=integration,
    )
    action_node_service.field_mappings.create(field=action_table_field, value="'Horse'")
    data_fixture.create_automation_node(
        workflow=workflow,
        service=action_node_service,
        type=LocalBaserowCreateRowNodeType.type,
    )

    action_table_model = action_table.get_model()
    assert action_table_model.objects.count() == 0

    AutomationWorkflowRunner().run(workflow, AutomationDispatchContext(workflow, {}))

    row = action_table_model.objects.first()
    assert getattr(row, action_table_field.db_column) == "Horse"
