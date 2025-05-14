from unittest.mock import patch

import pytest

from baserow.contrib.automation.nodes.node_types import (
    LocalBaserowCreateRowNodeType,
    service_backed_automation_nodes,
    signal_triggered_automation_triggers,
)
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.core.exceptions import InstanceTypeDoesNotExist


@pytest.mark.django_db
def test_service_backed_automation_nodes():
    result = service_backed_automation_nodes()

    assert isinstance(result[0], LocalBaserowCreateRowNodeType)


@pytest.mark.parametrize("automation_node_type", signal_triggered_automation_triggers())
def test_registering_signal_trigger_type_connects_to_signal(automation_node_type):
    try:
        automation_node_type_registry.get(automation_node_type.type)
    except InstanceTypeDoesNotExist:
        automation_node_type_registry.register(automation_node_type)
    registered_handlers = [
        receiver[1]() for receiver in automation_node_type.signal.receivers
    ]
    assert automation_node_type.handler in registered_handlers


@pytest.mark.parametrize("automation_node_type", signal_triggered_automation_triggers())
def test_unregistering_signal_trigger_type_disconnects_from_signal(
    automation_node_type,
):
    automation_node_type_registry.unregister(automation_node_type.type)
    registered_handlers = [
        receiver[1]() for receiver in automation_node_type.signal.receivers
    ]
    assert automation_node_type.handler not in registered_handlers


@patch(
    "baserow.contrib.automation.nodes.receivers.AutomationWorkflowHandler.run_workflow"
)
@pytest.mark.django_db
@pytest.mark.parametrize("automation_node_type", signal_triggered_automation_triggers())
def test_triggering_local_baserow_signal_trigger_enqueues_workflow_run(
    mock_run_workflow, automation_node_type, data_fixture
):
    registered_handlers = [
        receiver[1]() for receiver in automation_node_type.signal.receivers
    ]
    for handler in registered_handlers:
        if handler != automation_node_type.handler:
            automation_node_type.signal.disconnect(handler)

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table_issuing_signal = data_fixture.create_database_table(database=database)
    automation = data_fixture.create_automation_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        application=automation, authorized_user=user
    )
    workflow = data_fixture.create_automation_workflow(automation=automation)
    service = data_fixture.create_local_baserow_rows_created_service(
        integration=integration,
        table=table_issuing_signal,
    )
    data_fixture.create_automation_node(
        workflow=workflow, service=service, node_type=automation_node_type.type
    )
    automation_node_type.signal.send(
        None, table=table_issuing_signal, foo="bar", bar="baz"
    )
    mock_run_workflow.assert_called_once()

    for handler in registered_handlers:
        if handler != automation_node_type.handler:
            automation_node_type.signal.connect(handler)
