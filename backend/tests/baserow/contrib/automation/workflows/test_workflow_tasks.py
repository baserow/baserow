from unittest.mock import patch

import pytest

from baserow.contrib.automation.workflows.tasks import run_workflow
from baserow.core.services.exceptions import DispatchException


@patch("baserow.contrib.automation.workflows.tasks.logger")
@pytest.mark.django_db
def test_run_workflow_handles_error(mock_logger, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = data_fixture.create_local_baserow_integration(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    trigger_table = data_fixture.create_database_table(database=database)
    action_table = data_fixture.create_database_table(database=database)
    action_table_field = data_fixture.create_text_field(table=action_table)
    workflow = data_fixture.create_automation_workflow(user=user)
    data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=workflow,
        service=data_fixture.create_local_baserow_rows_created_service(
            table=trigger_table,
            integration=integration,
        ),
    )
    action_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
        service=data_fixture.create_local_baserow_upsert_row_service(
            table=action_table,
            integration=integration,
        ),
    )
    action_node.service.field_mappings.create(field=action_table_field, value="'Horse'")

    with patch.object(
        action_node.get_type(), "dispatch", side_effect=DispatchException("Test error")
    ):
        run_workflow(workflow.id, None)

    mock_logger.error.assert_called_once_with(
        f"Error while running workflow {workflow.id}: "
        f"The node {action_node.id} has a misconfigured service. Test error"
    )
