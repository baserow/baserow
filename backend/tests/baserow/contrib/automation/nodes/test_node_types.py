from unittest.mock import MagicMock, patch

import pytest

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.nodes.node_types import AutomationNodeTriggerType
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.core.exceptions import InstanceTypeDoesNotExist


def test_automation_node_type_is_replaceable_with():
    trigger_node_type = automation_node_type_registry.get("rows_created")
    update_trigger_node_type = automation_node_type_registry.get("rows_updated")
    action_node_type = automation_node_type_registry.get("create_row")
    update_action_node_type = automation_node_type_registry.get("update_row")

    assert trigger_node_type.is_replaceable_with(update_trigger_node_type)
    assert not trigger_node_type.is_replaceable_with(update_action_node_type)
    assert action_node_type.is_replaceable_with(update_action_node_type)
    assert not action_node_type.is_replaceable_with(update_trigger_node_type)


@pytest.mark.django_db
@patch(
    "baserow.contrib.automation.workflows.service.AutomationWorkflowService.run_workflow"
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

    node.get_type().on_event(service_queryset, event_payload, user=user)
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


def signal_trigger_node_types():
    return [
        node_type
        for node_type in automation_node_type_registry.get_all()
        if issubclass(node_type.__class__, AutomationNodeTriggerType)
    ]


@pytest.mark.parametrize("node_type", signal_trigger_node_types())
def test_registering_signal_node_type_connects_to_signal(node_type):
    try:
        automation_node_type_registry.get(node_type.type)
    except InstanceTypeDoesNotExist:
        automation_node_type_registry.register(node_type)
    service_type = node_type.get_service_type()
    registered_handlers = [receiver[1]() for receiver in service_type.signal.receivers]
    assert service_type.handler in registered_handlers


@pytest.mark.parametrize("node_type", signal_trigger_node_types())
def test_unregistering_signal_node_type_disconnects_from_signal(node_type):
    automation_node_type_registry.unregister(node_type.type)
    service_type = node_type.get_service_type()
    registered_handlers = [receiver[1]() for receiver in service_type.signal.receivers]
    assert service_type.handler not in registered_handlers


@pytest.mark.django_db
def test_automation_node_type_update_row_prepare_values_with_instance(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user, type="update_row")

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user, instance=node)
    assert result == {"service": node.service}


@pytest.mark.django_db
def test_automation_node_type_update_row_prepare_values_without_instance(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user, type="update_row")

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user)

    # Since we didn't pass in a service, a new service is created
    new_service = result["service"]
    assert isinstance(new_service, type(node.service))
    assert new_service.id != node.service.id


@patch("baserow.contrib.automation.nodes.registries.ServiceHandler.dispatch_service")
@pytest.mark.django_db
def test_automation_node_type_update_row_dispatch(mock_dispatch, data_fixture):
    mock_dispatch_result = MagicMock()
    mock_dispatch.return_value = mock_dispatch_result

    user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user, type="update_row")

    dispatch_context = AutomationDispatchContext(node.workflow, None)
    result = node.get_type().dispatch(node, dispatch_context)

    assert result == mock_dispatch_result
    mock_dispatch.assert_called_once_with(node.service.specific, dispatch_context)


@pytest.mark.django_db
def test_automation_node_type_delete_row_prepare_values_with_instance(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user, type="delete_row")

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user, instance=node)
    assert result == {"service": node.service}


@pytest.mark.django_db
def test_automation_node_type_delete_row_prepare_values_without_instance(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user, type="delete_row")

    values = {"service": {}}
    result = node.get_type().prepare_values(values, user)

    # Since we didn't pass in a service, a new service is created
    new_service = result["service"]

    assert isinstance(new_service, type(node.service))
    assert new_service.id != node.service.id


@patch("baserow.contrib.automation.nodes.registries.ServiceHandler.dispatch_service")
@pytest.mark.django_db
def test_automation_node_type_delete_row_dispatch(mock_dispatch, data_fixture):
    mock_dispatch_result = MagicMock()
    mock_dispatch.return_value = mock_dispatch_result

    user, _ = data_fixture.create_user_and_token()
    node = data_fixture.create_automation_node(user=user, type="delete_row")

    dispatch_context = AutomationDispatchContext(node.workflow, None)
    result = node.get_type().dispatch(node, dispatch_context)

    assert result == mock_dispatch_result
    mock_dispatch.assert_called_once_with(node.service.specific, dispatch_context)
