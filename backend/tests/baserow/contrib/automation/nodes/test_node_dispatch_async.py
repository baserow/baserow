from unittest.mock import ANY, patch

import pytest
from celery.canvas import Signature

from baserow.config.celery import clear_local
from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.models import (
    AutomationNodeHistory,
    AutomationNodeResult,
    AutomationWorkflowHistory,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.workflows.tasks import handle_workflow_dispatch_done
from baserow.core.services.exceptions import UnexpectedDispatchException
from baserow.test_utils.helpers import AnyInt, AnyStr

TRIGGER_NODE_TYPE_PATH = (
    "baserow.contrib.automation.nodes.node_types.LocalBaserowRowsCreatedNodeTriggerType"
)
NODE_HANDLER_PATH = "baserow.contrib.automation.nodes.handler"


def assert_dispatches_next_node(result, *expected_tasks):
    """
    Helper to assert that the correct signature is returned.

    expected_tasks are tuples, e.g.: (node, history, iterations)
    """

    assert isinstance(result, Signature)
    assert len(result.tasks) == len(expected_tasks)
    for i, (node, history, iterations) in enumerate(expected_tasks):
        task = result.tasks[i]
        if hasattr(task, "tasks"):
            assert len(task.tasks) == 1
            task = task.tasks[0]
        assert task.args == (node.id, history.id, iterations)


def execute_dispatch_signature_tree(result):
    """
    Execute the returned Celery canvas in-process by recursively dispatching each
    leaf node in order.
    """

    if result is None:
        return

    assert isinstance(result, Signature)

    if hasattr(result, "tasks"):
        for task in result.tasks:
            execute_dispatch_signature_tree(task)
        return

    next_result = AutomationNodeHandler().dispatch_node(*result.args)
    clear_local()
    execute_dispatch_signature_tree(next_result)


def create_workflow(
    data_fixture,
    user=None,
    action_node_type="create_row",
    action_node_service_value=None,
):
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

    action_table_row = None

    if action_node_type == "create_row":
        action_node = data_fixture.create_local_baserow_create_row_action_node(
            workflow=workflow,
            previous_node=trigger,
            service=data_fixture.create_local_baserow_upsert_row_service(
                table=action_table,
                integration=integration,
            ),
        )
    elif action_node_type == "update_row" and action_node_service_value:
        action_table_row = action_table.get_model().objects.create(
            **{f"field_{action_table_field.id}": action_node_service_value}
        )
        action_node = data_fixture.create_local_baserow_update_row_action_node(
            workflow=workflow,
            previous_node=trigger,
            service=data_fixture.create_local_baserow_upsert_row_service(
                table=action_table,
                integration=integration,
                row_id=action_table_row.id,
            ),
        )
    elif action_node_type == "delete_row":
        action_table_row = action_table.get_model().objects.create(
            **{f"field_{action_table_field.id}": action_node_service_value}
        )
        action_node = data_fixture.create_local_baserow_delete_row_action_node(
            workflow=workflow,
            previous_node=trigger,
            service=data_fixture.create_local_baserow_delete_row_service(
                table=action_table,
                integration=integration,
                row_id=action_table_row.id,
            ),
        )

    if action_node_type in ("create_row", "update_row"):
        action_node.service.field_mappings.create(
            field=action_table_field,
            value=f"get('previous_node.{trigger.id}.0.{trigger_table_field_a.db_column}')",
        )

    history = create_workflow_history(
        data_fixture, workflow, [trigger_table_field_a, trigger_table_field_b]
    )

    return {
        "user": "user",
        "integration": integration,
        "workflow": workflow,
        "trigger_node": trigger,
        "action_node": action_node,
        "workflow_history": history,
        "action_table": action_table,
        "action_table_field": action_table_field,
        "action_table_row": action_table_row,
        "trigger_table": trigger_table,
        "trigger_table_field_a": trigger_table_field_a,
        "trigger_table_field_b": trigger_table_field_b,
    }


def create_workflow_history(data_fixture, workflow, trigger_table_fields):
    original_workflow = workflow.get_original()
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
def test_dispatch_node_service_error(data_fixture):
    user = data_fixture.create_user()
    trigger_node = data_fixture.create_local_baserow_rows_created_trigger_node(
        user=user
    )
    # create action node without any table configured
    data_fixture.create_local_baserow_create_row_action_node(
        workflow=trigger_node.workflow
    )
    original_workflow = trigger_node.workflow.get_original()

    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=original_workflow
    )

    result = AutomationNodeHandler().dispatch_node(
        trigger_node.id,
        history_id=workflow_history.id,
    )
    assert result is None

    workflow_history.refresh_from_db()
    error = "is misconfigured and cannot be dispatched"
    assert error in workflow_history.message
    assert workflow_history.status == HistoryStatusChoices.ERROR

    node_history = AutomationNodeHistory.objects.get(workflow_history=workflow_history)
    assert error in node_history.message
    assert node_history.status == HistoryStatusChoices.ERROR


@pytest.mark.django_db
@patch(f"{TRIGGER_NODE_TYPE_PATH}.dispatch")
@patch(f"{NODE_HANDLER_PATH}.logger")
def test_dispatch_node_unexpected_error(mock_logger, mock_dispatch, data_fixture):
    mock_dispatch.side_effect = ValueError("Unexpected error!")

    data = create_workflow(data_fixture)
    trigger_node = data["trigger_node"]
    workflow_history = data["workflow_history"]

    result = AutomationNodeHandler().dispatch_node(
        trigger_node.id,
        history_id=workflow_history.id,
    )
    assert result is None
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


@pytest.mark.django_db
@patch(f"{TRIGGER_NODE_TYPE_PATH}.dispatch")
@patch(f"{NODE_HANDLER_PATH}.logger")
def test_dispatch_node_expected_error(mock_logger, mock_dispatch, data_fixture):
    mock_dispatch.side_effect = UnexpectedDispatchException("Mock external API error")

    data = create_workflow(data_fixture)
    trigger_node = data["trigger_node"]
    workflow_history = data["workflow_history"]

    result = AutomationNodeHandler().dispatch_node(
        trigger_node.id,
        history_id=workflow_history.id,
    )
    assert result is None
    workflow_history.refresh_from_db()
    error = (
        f"Error while running workflow {trigger_node.workflow.id}. "
        "Error: Mock external API error"
    )

    mock_logger.warning.assert_called_once_with(error)
    # Ensure error/exception are not logged, since that would cause
    # Sentry to create an issue.
    mock_logger.error.assert_not_called()
    mock_logger.exception.assert_not_called()

    assert error in workflow_history.message
    assert workflow_history.status == HistoryStatusChoices.ERROR

    node_history = AutomationNodeHistory.objects.get(workflow_history=workflow_history)
    assert error in node_history.message
    assert node_history.status == HistoryStatusChoices.ERROR


@pytest.mark.django_db
def test_dispatch_node_dispatches_trigger(data_fixture):
    data = create_workflow(data_fixture)
    trigger_node = data["trigger_node"]
    action_node = data["action_node"]
    workflow_history = data["workflow_history"]

    result = AutomationNodeHandler().dispatch_node(
        trigger_node.id,
        history_id=workflow_history.id,
    )

    handle_workflow_dispatch_done(history_id=workflow_history.id)
    workflow_history.refresh_from_db()
    assert workflow_history.message == ""
    assert workflow_history.status == HistoryStatusChoices.SUCCESS

    node_history = AutomationNodeHistory.objects.get(workflow_history=workflow_history)
    assert node_history.message == ""
    assert node_history.status == HistoryStatusChoices.SUCCESS

    node_result = AutomationNodeResult.objects.get(node_history=node_history)
    assert node_result.iteration == 0
    assert node_result.result == workflow_history.event_payload

    assert_dispatches_next_node(result, (action_node, workflow_history, None))


@pytest.mark.django_db
def test_dispatch_node_dispatches_action_create_row(data_fixture):
    data = create_workflow(data_fixture)
    trigger_node = data["trigger_node"]
    action_node = data["action_node"]
    workflow_history = data["workflow_history"]
    action_table = data["action_table"]
    action_table_field = data["action_table_field"]

    # First dispatch the trigger
    result = AutomationNodeHandler().dispatch_node(
        trigger_node.id,
        history_id=workflow_history.id,
    )

    assert_dispatches_next_node(result, (action_node, workflow_history, None))

    assert action_table.get_model().objects.all().count() == 0

    # Next dispatch the action
    result = AutomationNodeHandler().dispatch_node(
        action_node.id,
        history_id=workflow_history.id,
    )
    assert result is None

    # Make sure the action dispatched correctly
    value = getattr(
        action_table.get_model().objects.all()[0], action_table_field.db_column
    )
    assert value == "Apple"

    handle_workflow_dispatch_done(history_id=workflow_history.id)
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


@pytest.mark.django_db
def test_dispatch_node_dispatches_iterator_children(data_fixture):
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
    result = AutomationNodeHandler().dispatch_node(
        trigger_node.id,
        history_id=workflow_history.id,
    )
    assert_dispatches_next_node(result, (iterator_node, workflow_history, None))

    assert iterator_child_1_table.get_model().objects.all().count() == 0

    # Next dispatch the iterator node
    result = AutomationNodeHandler().dispatch_node(
        iterator_node.id,
        history_id=workflow_history.id,
    )
    # Clear the local cache between dispatch_node() calls to simulate
    # how Celery clears the local cache between tasks in production.
    clear_local()

    # result is a chain of chords
    assert isinstance(result, Signature)

    # Make sure the iterator children's node history and results are persisted.
    # There are two rows in the payload, so we expect two histories.
    assert AutomationNodeHistory.objects.filter(node=iterator_child_1_node).count() == 0

    result = AutomationNodeHandler().dispatch_node(
        iterator_child_1_node.id,
        history_id=workflow_history.id,
        current_iterations={iterator_node.id: 0},
    )
    clear_local()

    assert_dispatches_next_node(
        result, (iterator_child_2_node, workflow_history, {iterator_node.id: 0})
    )

    # Manually dispatch child 1 for iteration 1
    result = AutomationNodeHandler().dispatch_node(
        iterator_child_1_node.id,
        history_id=workflow_history.id,
        current_iterations={iterator_node.id: 1},
    )
    clear_local()

    assert_dispatches_next_node(
        result, (iterator_child_2_node, workflow_history, {iterator_node.id: 1})
    )

    node_histories = AutomationNodeHistory.objects.filter(
        node=iterator_child_1_node, status=HistoryStatusChoices.SUCCESS
    ).order_by("id")
    assert len(node_histories) == 2

    # workflow history should still be "started", since the final node
    # hasn't been dispatched yet.
    workflow_history.refresh_from_db()
    assert workflow_history.status == HistoryStatusChoices.STARTED

    # Dispatch the after iteration node
    result = AutomationNodeHandler().dispatch_node(
        after_iteration_node.id,
        history_id=workflow_history.id,
    )

    # There are no next nodes
    assert result is None

    # workflow history should be finally be updated as success
    handle_workflow_dispatch_done(history_id=workflow_history.id)
    workflow_history.refresh_from_db()
    assert workflow_history.message == ""
    assert workflow_history.status == HistoryStatusChoices.SUCCESS


@pytest.mark.django_db
def test_dispatch_node_fully_dispatches_nested_iterator_workflow(data_fixture):
    data = data_fixture.nested_iterator_graph_fixture()
    trigger_node = data["trigger_node"]
    trigger_table_fields = data["trigger_table_fields"]
    child_iterator_child_1_table = data["child_iterator_child_1_table"]
    child_iterator_child_1_table_fields = data["child_iterator_child_1_table_fields"]
    child_iterator_child_2_table = data["child_iterator_child_2_table"]
    child_iterator_child_2_table_fields = data["child_iterator_child_2_table_fields"]
    after_iteration_table = data["after_iteration_table"]

    original_workflow = trigger_node.workflow.get_original()
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=original_workflow,
        event_payload={
            "results": [
                {
                    "id": 100,
                    "order": "10.00000000000000000000",
                    trigger_table_fields[0].name: "Apple",
                    trigger_table_fields[1].name: [
                        {"Name": "Fuji", "Color": "Red"},
                        {"Name": "Granny Smith", "Color": "Green"},
                    ],
                },
                {
                    "id": 101,
                    "order": "20.00000000000000000000",
                    trigger_table_fields[0].name: "Banana",
                    trigger_table_fields[1].name: [
                        {"Name": "Cavendish", "Color": "Yellow"},
                        {"Name": "Plantain", "Color": "Green"},
                    ],
                },
            ],
            "has_next_page": False,
        },
    )

    result = AutomationNodeHandler().dispatch_node(
        trigger_node.id,
        history_id=workflow_history.id,
    )
    clear_local()
    execute_dispatch_signature_tree(result)

    handle_workflow_dispatch_done(history_id=workflow_history.id)

    workflow_history.refresh_from_db()
    assert workflow_history.message == ""
    assert workflow_history.status == HistoryStatusChoices.SUCCESS

    child_1_rows = list(
        child_iterator_child_1_table.get_model()
        .objects.order_by("id")
        .values_list(child_iterator_child_1_table_fields[0].db_column, flat=True)
    )
    assert child_1_rows == ["Fuji", "Granny Smith", "Cavendish", "Plantain"]

    child_2_rows = list(
        child_iterator_child_2_table.get_model()
        .objects.order_by("id")
        .values_list(child_iterator_child_2_table_fields[0].db_column, flat=True)
    )
    assert child_2_rows == ["Fuji", "Granny Smith", "Cavendish", "Plantain"]

    assert after_iteration_table.get_model().objects.count() == 1


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.automation_node_updated")
def test_dispatch_node_dispatches_trigger_simulation(
    mock_automation_node_updated,
    data_fixture,
):
    data = create_workflow(data_fixture)
    trigger_node = data["trigger_node"]
    trigger_table_field_a = data["trigger_table_field_a"]
    trigger_table_field_b = data["trigger_table_field_b"]

    workflow_history = data["workflow_history"]
    workflow_history.simulate_until_node = trigger_node
    workflow_history.save()

    assert trigger_node.service.specific.sample_data is None

    result = AutomationNodeHandler().dispatch_node(
        trigger_node.id,
        history_id=workflow_history.id,
    )

    # There are no next nodes
    assert result is None

    # Ensure workflow history is deleted, since we don't want history
    # entries for simulations.
    handle_workflow_dispatch_done(
        workflow_history.id, simulate_until_node_id=trigger_node.id
    )
    assert (
        AutomationWorkflowHistory.objects.filter(id=workflow_history.id).exists()
        is False
    )

    # Ensure the sample data is saved
    trigger_node.service.specific.refresh_from_db()
    assert trigger_node.service.specific.sample_data == {
        "data": {
            "results": [
                {
                    "id": AnyInt(),
                    "order": AnyStr(),
                    trigger_table_field_a.name: "Apple",
                    trigger_table_field_b.name: "Red",
                },
                {
                    "id": AnyInt(),
                    "order": AnyStr(),
                    trigger_table_field_a.name: "Banana",
                    trigger_table_field_b.name: "Yellow",
                },
            ],
            "has_next_page": False,
        },
        "status": 200,
        "output_uid": "",
    }

    mock_automation_node_updated.send.assert_called_once_with(
        ANY, user=None, node=trigger_node
    )


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.automation_node_updated")
def test_dispatch_node_dispatches_action_simulation(
    mock_automation_node_updated,
    data_fixture,
):
    data = create_workflow(data_fixture)
    trigger_node = data["trigger_node"]
    action_node = data["action_node"]
    action_table_field = data["action_table_field"]
    trigger_table_field_a = data["trigger_table_field_a"]
    trigger_table_field_b = data["trigger_table_field_b"]

    workflow_history = data["workflow_history"]
    workflow_history.simulate_until_node = action_node
    workflow_history.save()

    assert action_node.service.specific.sample_data is None

    # Simulate the trigger first so that the dispatch context can populate
    # previous_node_results from the database.
    result = AutomationNodeHandler().dispatch_node(
        trigger_node.id,
        history_id=workflow_history.id,
    )
    assert_dispatches_next_node(result, (action_node, workflow_history, None))

    # Make sure the trigger node simulation saves a history entry
    node_history = AutomationNodeHistory.objects.get(workflow_history=workflow_history)
    assert node_history.message == ""
    assert node_history.status == HistoryStatusChoices.SUCCESS

    node_result = AutomationNodeResult.objects.get(node_history=node_history)
    assert node_result.iteration == 0
    assert node_result.result == {
        "results": [
            {
                "id": AnyInt(),
                "order": AnyStr(),
                trigger_table_field_a.name: "Apple",
                trigger_table_field_b.name: "Red",
            },
            {
                "id": AnyInt(),
                "order": AnyStr(),
                trigger_table_field_a.name: "Banana",
                trigger_table_field_b.name: "Yellow",
            },
        ],
        "has_next_page": False,
    }

    # Now simulate the action
    result = AutomationNodeHandler().dispatch_node(
        action_node.id,
        history_id=workflow_history.id,
    )
    # There are no next nodes
    assert result is None

    # Ensure the sample data is saved
    action_node.service.specific.refresh_from_db()
    assert action_node.service.specific.sample_data == {
        "data": {
            action_table_field.name: "Apple",
            "id": AnyInt(),
            "order": AnyStr(),
        },
        "output_uid": "",
        "status": 200,
    }

    mock_automation_node_updated.send.assert_called_once_with(
        ANY, user=None, node=action_node
    )

    # Ensure workflow history is deleted, since we don't want history
    # entries for simulations.
    handle_workflow_dispatch_done(
        workflow_history.id, simulate_until_node_id=action_node.id
    )
    assert (
        AutomationWorkflowHistory.objects.filter(id=workflow_history.id).exists()
        is False
    )


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.automation_node_updated")
def test_dispatch_node_simulation_error_misconfigured_service_sends_node_updated_signal(
    mock_automation_node_updated,
    data_fixture,
):
    data = create_workflow(data_fixture)
    trigger_node = data["trigger_node"]
    action_node = data["action_node"]

    workflow_history = data["workflow_history"]
    workflow_history.simulate_until_node = action_node
    workflow_history.save()

    assert action_node.service.specific.sample_data is None

    # Simulate the trigger first so that the dispatch context can populate
    # previous_node_results from the database.
    result = AutomationNodeHandler().dispatch_node(
        trigger_node.id,
        history_id=workflow_history.id,
    )
    assert_dispatches_next_node(result, (action_node, workflow_history, None))

    # Break the action node's service
    action_node.service.specific.table = None
    action_node.service.specific.save()

    # Now simulate the action node, which should fail
    result = AutomationNodeHandler().dispatch_node(
        action_node.id,
        history_id=workflow_history.id,
    )
    assert result is None

    action_node.service.specific.refresh_from_db()
    assert action_node.service.specific.sample_data == {"_error": "No table selected"}

    # Make sure the node updated signal is sent
    mock_automation_node_updated.send.assert_called_once_with(
        ANY, user=None, node=action_node
    )


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.automation_node_updated")
def test_dispatch_node_simulation_error_dispatch_exception_sends_node_updated_signal(
    mock_automation_node_updated,
    data_fixture,
):
    data = create_workflow(data_fixture)
    trigger_node = data["trigger_node"]
    action_node = data["action_node"]

    workflow_history = data["workflow_history"]
    workflow_history.simulate_until_node = action_node
    workflow_history.save()

    assert action_node.service.specific.sample_data is None

    # Simulate the trigger first so that the dispatch context can populate
    # previous_node_results from the database.
    result = AutomationNodeHandler().dispatch_node(
        trigger_node.id,
        history_id=workflow_history.id,
    )
    assert_dispatches_next_node(result, (action_node, workflow_history, None))

    # Simulate an UnexpectedDispatchException
    node_type = action_node.get_type()
    with patch.object(
        type(node_type),
        "dispatch",
        side_effect=UnexpectedDispatchException("Mock dispatch error"),
    ):
        result = AutomationNodeHandler().dispatch_node(
            action_node.id,
            history_id=workflow_history.id,
        )

    assert result is None

    action_node.service.specific.refresh_from_db()
    assert action_node.service.specific.sample_data is None

    # Make sure the node updated signal is sent
    mock_automation_node_updated.send.assert_called_once_with(
        ANY, user=None, node=action_node
    )


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.automation_node_updated")
def test_dispatch_node_simulation_error_unknown_exception_sends_node_updated_signal(
    mock_automation_node_updated,
    data_fixture,
):
    data = create_workflow(data_fixture)
    trigger_node = data["trigger_node"]
    action_node = data["action_node"]

    workflow_history = data["workflow_history"]
    workflow_history.simulate_until_node = action_node
    workflow_history.save()

    assert action_node.service.specific.sample_data is None

    # Simulate the trigger first so that the dispatch context can populate
    # previous_node_results from the database.
    result = AutomationNodeHandler().dispatch_node(
        trigger_node.id,
        history_id=workflow_history.id,
    )
    assert_dispatches_next_node(result, (action_node, workflow_history, None))

    # Simulate an unexpected error that is handled by the
    # `except Exception:` block.
    node_type = action_node.get_type()
    with patch.object(
        type(node_type), "dispatch", side_effect=ValueError("Mock unexpected error")
    ):
        result = AutomationNodeHandler().dispatch_node(
            action_node.id,
            history_id=workflow_history.id,
        )

    assert result is None

    action_node.service.specific.refresh_from_db()
    assert action_node.service.specific.sample_data is None

    # Make sure the node updated signal is sent
    mock_automation_node_updated.send.assert_called_once_with(
        ANY, user=None, node=action_node
    )


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.automation_node_updated")
def test_dispatch_node_dispatches_iterator_simulation(
    mock_automation_node_updated,
    data_fixture,
):
    data = data_fixture.iterator_graph_fixture()
    trigger_node = data["trigger_node"]
    trigger_table_fields = data["trigger_table_fields"]
    iterator_node = data["iterator_node"]
    iterator_child_1_table_fields = data["iterator_child_1_table_fields"]
    iterator_child_1_node = data["iterator_child_1_node"]
    iterator_child_2_node = data["iterator_child_2_node"]
    after_iteration_node = data["after_iteration_node"]

    workflow_history = create_workflow_history(
        data_fixture,
        trigger_node.workflow,
        trigger_table_fields,
    )
    workflow_history.simulate_until_node = iterator_child_2_node
    workflow_history.save()

    # Ensure that the iterator node and children don't yet have sample data
    assert iterator_child_2_node.service.specific.sample_data is None

    # Simulate the trigger first so that the dispatch context can populate
    # previous_node_results from the database.
    for node in [trigger_node, iterator_node]:
        result = AutomationNodeHandler().dispatch_node(
            node.id,
            history_id=workflow_history.id,
        )
        # Clear the local cache between dispatch_node() calls to simulate
        # how Celery clears the local cache between tasks in production.
        clear_local()

    assert_dispatches_next_node(
        result,
        (iterator_child_1_node, workflow_history, {iterator_node.id: 0}),
        (after_iteration_node, workflow_history, None),
    )

    for child_node in [iterator_child_1_node, iterator_child_2_node]:
        result = AutomationNodeHandler().dispatch_node(
            child_node.id,
            history_id=workflow_history.id,
            current_iterations={iterator_node.id: 0},
        )

    # No more nodes to dispatch
    assert result is None

    handle_workflow_dispatch_done(
        workflow_history.id, simulate_until_node_id=iterator_child_2_node.id
    )

    # Make sure the last iterator node simulation saves a history entry
    iterator_child_2_node.service.specific.refresh_from_db()
    assert iterator_child_2_node.service.specific.sample_data == {
        "data": {
            iterator_child_1_table_fields[0].name: AnyStr(),
            "id": AnyInt(),
            "order": AnyStr(),
        },
        "output_uid": "",
        "status": 200,
    }

    mock_automation_node_updated.send.assert_called_once_with(
        ANY, user=None, node=iterator_child_2_node
    )

    # Ensure workflow history is deleted, since we don't want history
    # entries for simulations.
    assert (
        AutomationWorkflowHistory.objects.filter(id=workflow_history.id).exists()
        is False
    )


@pytest.mark.django_db
def test_dispatch_node_dispatches_test_run(
    data_fixture,
):
    data = data_fixture.iterator_graph_fixture()
    trigger_node = data["trigger_node"]
    trigger_table_fields = data["trigger_table_fields"]
    iterator_node = data["iterator_node"]
    iterator_child_1_node = data["iterator_child_1_node"]
    iterator_child_2_node = data["iterator_child_2_node"]
    after_iteration_node = data["after_iteration_node"]

    workflow_history = create_workflow_history(
        data_fixture,
        trigger_node.workflow,
        trigger_table_fields,
    )

    for node in [trigger_node, iterator_node]:
        result = AutomationNodeHandler().dispatch_node(
            node.id,
            history_id=workflow_history.id,
        )
        # Clear the local cache between dispatch_node() calls to simulate
        # how Celery clears the local cache between tasks in production.
        clear_local()

    assert_dispatches_next_node(
        result,
        (iterator_child_1_node, workflow_history, {iterator_node.id: 0}),
        (iterator_child_1_node, workflow_history, {iterator_node.id: 1}),
        (after_iteration_node, workflow_history, None),
    )

    # workflow history should still be "started", since the after iteration node
    # hasn't been dispatched yet.
    workflow_history.refresh_from_db()
    assert workflow_history.status == HistoryStatusChoices.STARTED

    # Make sure all nodes have a history and node result
    for node in [
        trigger_node,
        iterator_node,
        iterator_child_1_node,
        iterator_child_2_node,
    ]:
        for index, node_history in enumerate(
            AutomationNodeHistory.objects.filter(
                workflow_history=workflow_history,
                node=node,
            )
        ):
            assert node_history.message == ""
            assert node_history.status == HistoryStatusChoices.SUCCESS

            node_result = AutomationNodeResult.objects.get(node_history=node_history)
            assert node_result.iteration == index
            assert len(node_result.result) > 0

    # Ensure workflow history is exists for test runs
    handle_workflow_dispatch_done(history_id=workflow_history.id)
    assert (
        AutomationWorkflowHistory.objects.filter(id=workflow_history.id).exists()
        is True
    )

    # Dispatch the after iteration node
    result = AutomationNodeHandler().dispatch_node(
        after_iteration_node.id,
        history_id=workflow_history.id,
    )
    # there are no next nodes
    assert result is None

    # workflow history should be finally be updated as success
    workflow_history.refresh_from_db()
    assert workflow_history.status == HistoryStatusChoices.SUCCESS


@pytest.mark.django_db
def test_dispatch_node_dispatches_action_update_row(data_fixture):
    data = create_workflow(
        data_fixture,
        action_node_type="update_row",
        action_node_service_value="foo",
    )
    trigger_node = data["trigger_node"]
    action_node = data["action_node"]
    workflow_history = data["workflow_history"]
    action_table = data["action_table"]
    action_table_field = data["action_table_field"]

    # The value before the action updates the table
    result = getattr(
        action_table.get_model().objects.all()[0], action_table_field.db_column
    )
    assert result == "foo"

    for node in [trigger_node, action_node]:
        result = AutomationNodeHandler().dispatch_node(
            node.id,
            history_id=workflow_history.id,
        )

    # there are no next nodes
    assert result is None

    # The value after the action updates the table
    result = getattr(
        action_table.get_model().objects.all()[0], action_table_field.db_column
    )
    # Comes from the event_payload in workflow history
    assert result == "Apple"

    handle_workflow_dispatch_done(history_id=workflow_history.id)
    workflow_history.refresh_from_db()
    assert workflow_history.message == ""
    assert workflow_history.status == HistoryStatusChoices.SUCCESS

    node_history = AutomationNodeHistory.objects.get(
        workflow_history=workflow_history,
        node=action_node,
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


@pytest.mark.django_db
def test_dispatch_node_dispatches_action_delete_row(data_fixture):
    data = create_workflow(
        data_fixture,
        action_node_type="delete_row",
    )
    trigger_node = data["trigger_node"]
    action_node = data["action_node"]
    workflow_history = data["workflow_history"]
    action_table = data["action_table"]

    # The row before it is deleted
    assert action_table.get_model().objects.all().count() == 1

    for node in [trigger_node, action_node]:
        result = AutomationNodeHandler().dispatch_node(
            node.id,
            history_id=workflow_history.id,
        )

    # there are no next nodes
    assert result is None

    # The row after it is deleted
    assert action_table.get_model().objects.all().count() == 0

    handle_workflow_dispatch_done(history_id=workflow_history.id)
    workflow_history.refresh_from_db()
    assert workflow_history.message == ""
    assert workflow_history.status == HistoryStatusChoices.SUCCESS

    node_history = AutomationNodeHistory.objects.get(
        workflow_history=workflow_history,
        node=action_node,
    )
    assert node_history.message == ""
    assert node_history.status == HistoryStatusChoices.SUCCESS

    node_result = AutomationNodeResult.objects.get(node_history=node_history)
    assert node_result.iteration == 0
    assert node_result.result == {}


@pytest.mark.django_db
def test_dispatch_node_dispatches_action_router(data_fixture):
    data = create_workflow(
        data_fixture,
        action_node_type="update_row",
        action_node_service_value="foo",
    )
    workflow = data["workflow"]
    trigger_node = data["trigger_node"]
    action_node = data["action_node"]
    workflow_history = data["workflow_history"]
    action_table = data["action_table"]
    action_table_field = data["action_table_field"]
    action_table_row = data["action_table_row"]
    integration = data["integration"]

    router_node = data_fixture.create_core_router_action_node(
        workflow=workflow,
        reference_node=action_node,
        position="south",
    )
    data_fixture.create_core_router_service_edge(
        service=router_node.service, label="Edge 1", condition="'false'"
    )
    edge_2 = data_fixture.create_core_router_service_edge(
        service=router_node.service,
        label="Edge 2",
        condition="'true'",
        skip_output_node=True,
    )
    edge_2_node = data_fixture.create_local_baserow_update_row_action_node(
        workflow=workflow,
        reference_node=router_node,
        position="south",
        output=edge_2.uid,
        service_kwargs={
            "table": action_table,
            "integration": integration,
            "row_id": action_table_row.id,
        },
    )
    edge_2_node.service.field_mappings.create(
        field=action_table_field, value="'Cherry'"
    )

    trigger_node.workflow.refresh_from_db()

    # The value before the router edge 2 updates the table
    result = getattr(
        action_table.get_model().objects.all()[0], action_table_field.db_column
    )
    assert result == "foo"

    for node in [trigger_node, action_node, router_node, edge_2_node]:
        result = AutomationNodeHandler().dispatch_node(
            node.id,
            history_id=workflow_history.id,
        )

    # there are no next nodes
    assert result is None

    # The value after the router edge 2 updates the table
    result = getattr(
        action_table.get_model().objects.all()[0], action_table_field.db_column
    )
    assert result == "Cherry"

    handle_workflow_dispatch_done(history_id=workflow_history.id)
    workflow_history.refresh_from_db()
    assert workflow_history.message == ""
    assert workflow_history.status == HistoryStatusChoices.SUCCESS

    node_history = AutomationNodeHistory.objects.get(
        workflow_history=workflow_history,
        node=edge_2_node,
    )
    assert node_history.message == ""
    assert node_history.status == HistoryStatusChoices.SUCCESS

    node_result = AutomationNodeResult.objects.get(node_history=node_history)
    assert node_result.iteration == 0
    assert node_result.result == {
        action_table_field.name: "Cherry",
        "id": AnyInt(),
        "order": AnyStr(),
    }


@pytest.mark.django_db(transaction=True)
def test_dispatch_node_with_advanced_formulas(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = data_fixture.create_local_baserow_integration(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    trigger_table, trigger_table_fields, _ = data_fixture.build_table(
        user=user,
        columns=[
            ("Food", "text"),
            ("Spiciness", "number"),
        ],
        rows=[
            ["Paneer Tikka", 5],
            ["Gobi Manchurian", 8],
        ],
    )

    action_table, action_table_fields, _ = data_fixture.build_table(
        database=database,
        user=user,
        columns=[("Name", "text")],
        rows=[],
    )
    workflow = data_fixture.create_automation_workflow(user, state="live")
    trigger = workflow.get_trigger()
    trigger_service = trigger.service.specific
    trigger_service.table = trigger_table
    trigger_service.integration = integration
    trigger_service.save()
    action_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
        service=data_fixture.create_local_baserow_upsert_row_service(
            table=action_table,
            integration=integration,
        ),
    )
    action_node.service.field_mappings.create(
        field=action_table_fields[0],
        value=(
            "concat('The comparison is ', "
            f"get('previous_node.{trigger.id}.0.{trigger_table_fields[1].db_column}') "
            "> 7)"
        ),
    )

    action_table_model = action_table.get_model()
    assert action_table_model.objects.count() == 0

    original_workflow = workflow.get_original()
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=original_workflow,
        event_payload={
            "results": [
                {
                    "id": 100,
                    "order": "10.00000000000000000000",
                    trigger_table_fields[0].name: "Paneer Tikka",
                    trigger_table_fields[1].name: 5,
                },
                {
                    "id": 101,
                    "order": "10.00000000000000000000",
                    trigger_table_fields[0].name: "Gobi Manchurian",
                    trigger_table_fields[1].name: 8,
                },
            ],
            "has_next_page": False,
        },
    )

    result = AutomationNodeHandler().dispatch_node(
        trigger.id,
        history_id=workflow_history.id,
    )
    assert_dispatches_next_node(result, (action_node, workflow_history, None))

    result = AutomationNodeHandler().dispatch_node(
        action_node.id,
        history_id=workflow_history.id,
    )
    assert result is None

    handle_workflow_dispatch_done(history_id=workflow_history.id)
    row = action_table_model.objects.first()
    assert getattr(row, action_table_fields[0].db_column) == "The comparison is false"


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.automation_node_updated")
def test_dispatch_node_dispatches_router_edge_simulation(
    mock_automation_node_updated,
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = data_fixture.create_local_baserow_integration(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    # Create trigger
    workflow = data_fixture.create_automation_workflow(
        user=user,
        trigger_type="local_baserow_rows_created",
    )
    trigger_node = workflow.get_trigger()
    trigger_table = data_fixture.create_database_table(database=database)
    trigger_table_field = data_fixture.create_text_field(table=trigger_table)
    trigger_service = trigger_node.service.specific
    trigger_service.table = trigger_table
    trigger_service.integration = integration
    trigger_service.save()

    # Create first router with two edges
    router_a = data_fixture.create_core_router_action_node(
        workflow=workflow,
        reference_node=trigger_node,
        position="south",
        label="Router A",
    )
    router_a_edge_1 = data_fixture.create_core_router_service_edge(
        service=router_a.service,
        label="Router A Edge 1",
        condition="'true'",
        skip_output_node=True,
    )
    data_fixture.create_core_router_service_edge(
        service=router_a.service,
        label="Router A Edge 2",
        condition="'false'",
    )

    # Create second router on edge_1 of router_a
    router_b = data_fixture.create_core_router_action_node(
        workflow=workflow,
        reference_node=router_a,
        position="south",
        output=router_a_edge_1.uid,
        label="Router B",
    )
    data_fixture.create_core_router_service_edge(
        service=router_b.service,
        label="Router B Edge 1",
        condition="'false'",
        skip_output_node=True,
    )
    router_b_edge_2 = data_fixture.create_core_router_service_edge(
        service=router_b.service,
        label="Router B Edge 2",
        condition="'true'",
        skip_output_node=True,
    )

    # Create action node on edge_2 of router_b
    action_table = data_fixture.create_database_table(database=database)
    action_table_field = data_fixture.create_text_field(table=action_table)
    action_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
        reference_node=router_b,
        position="south",
        output=router_b_edge_2.uid,
        label="Action node",
        service_kwargs={
            "table": action_table,
            "integration": integration,
        },
    )
    action_node.service.field_mappings.create(
        field=action_table_field,
        value="'Pumpkin Pie'",
    )

    # Ensure there is no sample data yet
    for node in [trigger_node, router_a, router_b, action_node]:
        assert node.service.specific.sample_data is None

    original_workflow = workflow.get_original()
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=original_workflow,
        event_payload={
            "results": [
                {
                    "id": 1,
                    "order": "1.00000000000000000000",
                    trigger_table_field.name: "Cherry Cake",
                }
            ],
            "has_next_page": False,
        },
    )
    workflow_history.simulate_until_node = action_node
    workflow_history.save()

    for node in [trigger_node, router_a, router_b, action_node]:
        result = AutomationNodeHandler().dispatch_node(
            node.id,
            history_id=workflow_history.id,
        )

    # there are no next nodes
    assert result is None

    # Verify sample_data is saved for the action node
    action_node.service.specific.refresh_from_db()
    assert action_node.service.specific.sample_data == {
        "data": {
            action_table_field.name: "Pumpkin Pie",
            "id": AnyInt(),
            "order": AnyStr(),
        },
        "output_uid": AnyStr(),
        "status": 200,
    }

    mock_automation_node_updated.send.assert_called_once_with(
        ANY, user=None, node=action_node
    )

    # Verify workflow history is deleted for simulations
    handle_workflow_dispatch_done(
        workflow_history.id, simulate_until_node_id=action_node.id
    )
    assert (
        AutomationWorkflowHistory.objects.filter(id=workflow_history.id).exists()
        is False
    )


@pytest.mark.django_db
def test_dispatch_node_sets_workflow_history_error(data_fixture):
    """
    Ensure that when a node raises an error, the workflow history status
    is correctly set to ERROR.
    """

    data = create_workflow(data_fixture)
    trigger_node = data["trigger_node"]
    action_node = data["action_node"]
    workflow_history = data["workflow_history"]

    # Trigger dispatches successfully
    result = AutomationNodeHandler().dispatch_node(
        trigger_node.id,
        history_id=workflow_history.id,
    )
    assert isinstance(result, Signature)

    # Cause the action node to fail by unsetting its table
    action_node.service.specific.table = None
    action_node.service.specific.save()

    result = AutomationNodeHandler().dispatch_node(
        action_node.id,
        history_id=workflow_history.id,
    )
    assert result is None

    # chord callback shouldn't overwrite ERROR with SUCCESS
    handle_workflow_dispatch_done(history_id=workflow_history.id)

    workflow_history.refresh_from_db()
    assert workflow_history.status == HistoryStatusChoices.ERROR
    assert "No table selected" in workflow_history.message


@pytest.mark.django_db
def test_dispatch_node_iterator_with_no_rows(data_fixture):
    """
    This test ensures that when the iterator node receives no nodes,
    an empty chain is not created (which would cause a crash).
    """

    # We want an Iterator node with no next-nodes. This is to ensure that when
    # an iterator receives no rows, it doesn't create an empty chain.
    data = data_fixture.iterator_graph_fixture(create_after_iteration_node=False)
    trigger_node = data["trigger_node"]
    trigger_table_fields = data["trigger_table_fields"]
    iterator_node = data["iterator_node"]
    iterator_child_1_node = data["iterator_child_1_node"]

    # Create workflow history with 0 rows in the event payload.
    original_workflow = trigger_node.workflow.get_original()

    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=original_workflow,
        event_payload={
            "results": [],
            "has_next_page": False,
        },
    )

    # Dispatch the trigger.
    result = AutomationNodeHandler().dispatch_node(
        trigger_node.id,
        history_id=workflow_history.id,
    )
    assert_dispatches_next_node(result, (iterator_node, workflow_history, None))

    # Dispatch the iterator.
    result = AutomationNodeHandler().dispatch_node(
        iterator_node.id,
        history_id=workflow_history.id,
    )
    # Ensure we never return an empty chain, which would cause
    # self.replace() to crash with an error.
    assert result is None


@pytest.mark.django_db
@patch(f"{NODE_HANDLER_PATH}.logger")
def test_dispatch_node_with_deleted_node(mock_logger, data_fixture):
    """
    In the rare case where a node is deleted between the time a dispatch
    is queued and when the task actually runs, we should handle this
    gracefully instead of crashing.
    """

    data = create_workflow(data_fixture)
    action_node = data["action_node"]
    history = data["workflow_history"]

    # delete the node to simulate a race condition
    action_node_id = action_node.id
    action_node.delete()

    result = AutomationNodeHandler().dispatch_node(action_node_id, history.id)
    assert result is None
    expected_error = (
        f"Node with ID {action_node_id} was not found. The node was likely "
        "deleted before the task was executed."
    )
    mock_logger.warning.assert_called_once_with(expected_error)
