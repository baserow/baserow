from unittest.mock import MagicMock, patch

import pytest

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)


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


@pytest.mark.django_db
def test_automation_node_type_create_row_prepare_values_with_instance(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user, type="create_row")

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user, instance=node)
    assert result == {"service": node.service}


@pytest.mark.django_db
def test_automation_node_type_create_row_prepare_values_without_instance(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user, type="create_row")

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user)

    # Since we didn't pass in a service, a new service is created
    new_service = result["service"]
    assert isinstance(new_service, type(node.service))
    assert new_service.id != node.service.id


@patch("baserow.contrib.automation.nodes.registries.ServiceHandler.dispatch_service")
@pytest.mark.django_db
def test_automation_node_type_create_row_dispatch(mock_dispatch, data_fixture):
    mock_dispatch_result = MagicMock()
    mock_dispatch.return_value = mock_dispatch_result

    user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user, type="create_row")

    dispatch_context = AutomationDispatchContext(node.workflow, None)
    result = node.get_type().dispatch(node, dispatch_context)

    assert result == mock_dispatch_result
    mock_dispatch.assert_called_once_with(node.service.specific, dispatch_context)


@pytest.mark.django_db
def test_automation_node_type_rows_created_prepare_values_with_instance(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user, type="rows_created")

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user, instance=node)
    assert result == {"service": node.service}


@pytest.mark.django_db
def test_service_node_type_rows_created_prepare_values_without_instance(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user, type="rows_created")

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user)

    # Since we didn't pass in a service, a new service is created
    new_service = result["service"]
    assert isinstance(new_service, type(node.service))
    assert new_service.id != node.service.id
