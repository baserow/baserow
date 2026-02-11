from unittest.mock import patch

import pytest

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.models import (
    AutomationNodeHistory,
    AutomationNodeResult,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.test_utils.helpers import AnyInt, AnyStr

TRIGGER_NODE_TYPE_PATH = (
    "baserow.contrib.automation.nodes.node_types.LocalBaserowRowsCreatedNodeTriggerType"
)
NODE_HANDLER_PATH = "baserow.contrib.automation.nodes.handler"


def create_workflow(data_fixture, user=None):
    if user is None:
        user = data_fixture.create_user()

    workspace = data_fixture.create_workspace(user=user)
    integration = data_fixture.create_local_baserow_integration(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    trigger_table = data_fixture.create_database_table(database=database)
    trigger_table_field_a = data_fixture.create_text_field(table=trigger_table)
    trigger_table_field_b = data_fixture.create_text_field(table=trigger_table)
    action_table = data_fixture.create_database_table(database=database)
    action_table_field = data_fixture.create_text_field(table=action_table)

    workflow = data_fixture.create_automation_workflow(
        user, trigger_type="local_baserow_rows_created"
    )
    trigger = workflow.get_trigger()
    trigger_service = trigger.service.specific
    trigger_service.table = trigger_table
    trigger_service.integration = integration
    trigger_service.save()

    action_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
        previous_node=trigger,
        service=data_fixture.create_local_baserow_upsert_row_service(
            table=action_table,
            integration=integration,
        ),
    )
    action_node.service.field_mappings.create(
        field=action_table_field,
        value=f"get('previous_node.{trigger.id}.0.{trigger_table_field_a.name}')",
    )

    history = create_workflow_history(
        data_fixture, workflow, [trigger_table_field_a, trigger_table_field_b]
    )

    return {
        "user": "user",
        "trigger_node": trigger,
        "action_node": action_node,
        "workflow_history": history,
        "action_table": action_table,
        "action_table_field": action_table_field,
        "trigger_table": trigger_table,
        "trigger_table_field_a": trigger_table_field_a,
        "trigger_table_field_b": trigger_table_field_b,
    }


def create_workflow_history(data_fixture, workflow, trigger_table_fields):
    original_workflow = AutomationWorkflowHandler().get_original_workflow(workflow)
    return data_fixture.create_automation_workflow_history(
        workflow=original_workflow,
        event_payload={
            "results": [
                {
                    "id": 100,
                    "order": "10.00000000000000000000",
                    trigger_table_fields[0].name: "Apple",
                    trigger_table_fields[1].name: "Red",
                },
                {
                    "id": 101,
                    "order": "10.00000000000000000000",
                    trigger_table_fields[0].name: "Banana",
                    trigger_table_fields[1].name: "Yellow",
                },
            ],
            "has_next_page": False,
        },
    )


@pytest.mark.django_db
@patch(f"{TRIGGER_NODE_TYPE_PATH}.dispatch")
def test_dispatch_node_async_returns_early_if_node_not_allowed(
    mock_dispatch, data_fixture
):
    data = create_workflow(data_fixture)
    trigger_node = data["trigger_node"]
    action_node = data["action_node"]
    workflow_history = data["workflow_history"]

    result = AutomationNodeHandler().dispatch_node_async(
        trigger_node.id,
        workflow_history.id,
        allowed_node_ids=[action_node.id],
    )

    assert result is None
    mock_dispatch.assert_not_called()


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.dispatch_node_celery_task")
def test_dispatch_node_async_service_error(mock_dispatch_task, data_fixture):
    user = data_fixture.create_user()
    trigger_node = data_fixture.create_local_baserow_rows_created_trigger_node(
        user=user
    )
    # create action node without any table configured
    data_fixture.create_local_baserow_create_row_action_node(
        workflow=trigger_node.workflow
    )
    original_workflow = AutomationWorkflowHandler().get_original_workflow(
        trigger_node.workflow
    )
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=original_workflow
    )

    AutomationNodeHandler().dispatch_node_async(
        trigger_node.id,
        history_id=workflow_history.id,
        allowed_node_ids=None,
    )
    workflow_history.refresh_from_db()
    error = "is misconfigured and cannot be dispatched"
    assert error in workflow_history.message
    assert workflow_history.status == HistoryStatusChoices.ERROR

    node_history = AutomationNodeHistory.objects.get(workflow_history=workflow_history)
    assert error in node_history.message
    assert node_history.status == HistoryStatusChoices.ERROR

    mock_dispatch_task.delay.assert_not_called()


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.dispatch_node_celery_task")
@patch(f"{TRIGGER_NODE_TYPE_PATH}.dispatch")
@patch(f"{NODE_HANDLER_PATH}.logger")
def test_dispatch_node_async_unexpected_error(
    mock_logger, mock_dispatch, mock_dispatch_task, data_fixture
):
    mock_dispatch.side_effect = ValueError("Unexpected error!")

    data = create_workflow(data_fixture)
    trigger_node = data["trigger_node"]
    workflow_history = data["workflow_history"]

    AutomationNodeHandler().dispatch_node_async(
        trigger_node.id,
        history_id=workflow_history.id,
        allowed_node_ids=None,
    )
    workflow_history.refresh_from_db()
    error = (
        f"Unexpected error while running workflow {trigger_node.workflow.id}. "
        "Error: Unexpected error!"
    )
    mock_logger.exception.assert_called_once_with(error)
    assert error in workflow_history.message
    assert workflow_history.status == HistoryStatusChoices.ERROR

    node_history = AutomationNodeHistory.objects.get(workflow_history=workflow_history)
    assert error in node_history.message
    assert node_history.status == HistoryStatusChoices.ERROR

    mock_dispatch_task.delay.assert_not_called()


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.dispatch_node_celery_task")
def test_dispatch_node_async_dispatches_trigger(mock_dispatch_task, data_fixture):
    data = create_workflow(data_fixture)
    trigger_node = data["trigger_node"]
    action_node = data["action_node"]
    workflow_history = data["workflow_history"]

    AutomationNodeHandler().dispatch_node_async(
        trigger_node.id,
        history_id=workflow_history.id,
        allowed_node_ids=None,
    )

    workflow_history.refresh_from_db()
    assert workflow_history.message == ""
    assert workflow_history.status == HistoryStatusChoices.STARTED

    node_history = AutomationNodeHistory.objects.get(workflow_history=workflow_history)
    assert node_history.message == ""
    assert node_history.status == HistoryStatusChoices.SUCCESS

    node_result = AutomationNodeResult.objects.get(node_history=node_history)
    assert node_result.iteration == 0
    assert node_result.result == workflow_history.event_payload

    mock_dispatch_task.delay.assert_called_once_with(
        action_node.id,
        workflow_history.id,
        None,
        current_iterations=None,
    )


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.dispatch_node_celery_task")
def test_dispatch_node_async_dispatches_action(mock_dispatch_task, data_fixture):
    data = create_workflow(data_fixture)
    trigger_node = data["trigger_node"]
    action_node = data["action_node"]
    workflow_history = data["workflow_history"]
    action_table = data["action_table"]
    action_table_field = data["action_table_field"]

    # First dispatch the trigger
    AutomationNodeHandler().dispatch_node_async(
        trigger_node.id,
        history_id=workflow_history.id,
        allowed_node_ids=None,
    )
    mock_dispatch_task.delay.assert_called_once_with(
        action_node.id,
        workflow_history.id,
        None,
        current_iterations=None,
    )

    assert action_table.get_model().objects.all().count() == 0

    # Next dispatch the action
    mock_dispatch_task.reset_mock()
    AutomationNodeHandler().dispatch_node_async(
        action_node.id,
        history_id=workflow_history.id,
        allowed_node_ids=None,
    )

    # Make sure the action dispatched correctly
    result = getattr(
        action_table.get_model().objects.all()[0], action_table_field.db_column
    )
    assert result == "Apple"

    workflow_history.refresh_from_db()
    assert workflow_history.message == ""
    assert workflow_history.status == HistoryStatusChoices.SUCCESS

    node_history = (
        AutomationNodeHistory.objects.filter(workflow_history=workflow_history)
        .order_by("-id")
        .first()
    )
    assert node_history.message == ""
    assert node_history.status == HistoryStatusChoices.SUCCESS

    node_result = AutomationNodeResult.objects.get(node_history=node_history)
    assert node_result.iteration == 0
    assert node_result.result == {
        action_table_field.name: "Apple",
        "id": AnyInt(),
        "order": AnyStr(),
    }

    # There are no next nodes
    mock_dispatch_task.delay.assert_not_called()


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.dispatch_node_celery_task")
def test_dispatch_node_async_dispatches_children(mock_dispatch_task, data_fixture):
    data = data_fixture.iterator_graph_fixture()
    trigger_node = data["trigger_node"]
    trigger_table_fields = data["trigger_table_fields"]
    iterator_node = data["iterator_node"]
    iterator_child_1_node = data["iterator_child_1_node"]
    iterator_child_1_table = data["iterator_child_1_table"]
    iterator_child_1_table_fields = data["iterator_child_1_table_fields"]
    iterator_child_2_node = data["iterator_child_2_node"]
    iterator_child_2_table_fields = data["iterator_child_2_table_fields"]
    after_iteration_node = data["after_iteration_node"]

    workflow_history = create_workflow_history(
        data_fixture,
        trigger_node.workflow,
        trigger_table_fields,
    )

    # First dispatch the trigger
    AutomationNodeHandler().dispatch_node_async(
        trigger_node.id,
        history_id=workflow_history.id,
        allowed_node_ids=None,
    )
    mock_dispatch_task.delay.assert_called_once_with(
        iterator_node.id,
        workflow_history.id,
        None,
        current_iterations=None,
    )

    assert iterator_child_1_table.get_model().objects.all().count() == 0

    # Next dispatch the iterator node
    mock_dispatch_task.reset_mock()
    AutomationNodeHandler().dispatch_node_async(
        iterator_node.id,
        history_id=workflow_history.id,
        allowed_node_ids=None,
    )

    # Make sure the iterator children's node history and results are persisted.
    # There are two rows in the payload, so we expect two histories.
    test_cases = [
        (iterator_child_1_node, iterator_child_1_table_fields, ["Apple", "Banana"]),
        (iterator_child_2_node, iterator_child_2_table_fields, ["Red", "Yellow"]),
    ]
    for node, table_fields, expected_values in test_cases:
        node_histories = AutomationNodeHistory.objects.filter(
            node=node, status=HistoryStatusChoices.SUCCESS
        ).order_by("id")
        assert len(node_histories) == 2

        for index, (node_history, expected_value) in enumerate(
            zip(node_histories, expected_values)
        ):
            assert node_history.message == ""
            assert node_history.status == HistoryStatusChoices.SUCCESS

            node_result = AutomationNodeResult.objects.get(node_history=node_history)
            assert node_result.iteration == index
            assert node_result.result == {
                table_fields[0].name: expected_value,
                "id": AnyInt(),
                "order": AnyStr(),
            }

    # After the iterator nodes are dispatched sync, the after_iteration_node
    # should have been dispatched async.
    mock_dispatch_task.delay.assert_called_once_with(
        after_iteration_node.id,
        workflow_history.id,
        None,
        current_iterations=None,
    )

    # And the workflow history is updated correctly.
    workflow_history.refresh_from_db()
    assert workflow_history.message == ""
    assert workflow_history.status == HistoryStatusChoices.SUCCESS
