from unittest.mock import patch

import pytest


@pytest.mark.django_db
@patch(
    "baserow.contrib.automation.nodes.node_types.AutomationWorkflowHandler.run_workflow"
)
def test_automation_service_node_trigger_type_on_event(mock_run_workflow, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    service = data_fixture.create_local_baserow_rows_created_service(
        table=table,
    )
    workflow = data_fixture.create_automation_workflow(published=True)
    node = data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=workflow, service=service
    )

    service_queryset = service.get_type().model_class.objects.filter(table=table)
    event_payload = [
        {
            "id": 1,
            "order": "1.00000000000000000000",
            f"field_1": "Community Engagement",
        },
        {
            "id": 2,
            "order": "2.00000000000000000000",
            f"field_1": "Construction",
        },
    ]

    node.get_type().on_event(service_queryset, event_payload)
    mock_run_workflow.assert_called_once()
