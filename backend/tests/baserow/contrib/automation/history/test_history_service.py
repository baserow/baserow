import pytest

from baserow.contrib.automation.history.exceptions import (
    AutomationNodeHistoryDoesNotExist,
    AutomationWorkflowHistoryDoesNotExist,
    AutomationWorkflowHistoryNodeResultDoesNotExist,
)
from baserow.contrib.automation.history.service import AutomationHistoryService
from baserow.core.exceptions import UserNotInWorkspace


@pytest.mark.django_db
def test_get_workflow_histories_permission_error(data_fixture):
    user = data_fixture.create_user()
    history = data_fixture.create_workflow_history(user=user)

    # Different user
    user_2 = data_fixture.create_user()

    with pytest.raises(UserNotInWorkspace) as e:
        AutomationHistoryService().get_workflow_histories(user_2, history.workflow.id)

    assert str(e.value) == (
        f"User {user_2.email} doesn't belong to "
        f"workspace {history.workflow.automation.workspace}."
    )


@pytest.mark.django_db
def test_get_workflow_histories_returns_ordered_histories(data_fixture):
    user = data_fixture.create_user()
    original_workflow = data_fixture.create_automation_workflow(user=user)

    history_1 = data_fixture.create_workflow_history(
        original_workflow=original_workflow
    )
    history_2 = data_fixture.create_workflow_history(
        original_workflow=original_workflow
    )

    result = AutomationHistoryService().get_workflow_histories(
        user, original_workflow.id
    )

    assert list(result) == [history_2, history_1]


@pytest.mark.django_db
def test_get_child_node_histories(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    trigger_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=trigger
    )

    (
        node_histories,
        parent_map,
        error_ancestor_ids,
        edge_labels,
    ) = AutomationHistoryService().get_child_node_histories(
        user, workflow_history.id, parent_node_id=None
    )

    assert node_histories == [trigger_history]
    assert trigger.id in parent_map
    assert parent_map[trigger.id] is None
    assert error_ancestor_ids == set()
    assert edge_labels == {}


@pytest.mark.django_db
def test_get_child_node_histories_permission_error(data_fixture):
    """
    A user that doesn't belong to the workflow's workspace can't read
    its node histories.
    """

    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    other_user = data_fixture.create_user()

    with pytest.raises(UserNotInWorkspace):
        AutomationHistoryService().get_child_node_histories(
            other_user,
            workflow_history.id,
            parent_node_id=None,
        )


@pytest.mark.django_db
def test_get_child_node_histories_workflow_history_doesnt_exist(data_fixture):
    user = data_fixture.create_user()

    with pytest.raises(AutomationWorkflowHistoryDoesNotExist):
        AutomationHistoryService().get_child_node_histories(
            user,
            workflow_history_id=999999,
            parent_node_id=None,
        )


@pytest.mark.django_db
def test_get_child_node_histories_returns_children_of_parent(data_fixture):
    """
    Passing a parent_node_id scopes the result to that container's
    immediate children.
    """

    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    iterator = data_fixture.create_core_iterator_action_node(workflow=workflow)
    child_in_iterator = data_fixture.create_automation_node(
        workflow=workflow, reference_node=iterator, position="child"
    )
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=iterator
    )
    child_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=child_in_iterator
    )

    (
        node_histories,
        parent_map,
        _,
        _,
    ) = AutomationHistoryService().get_child_node_histories(
        user, workflow_history.id, parent_node_id=iterator.id
    )

    assert node_histories == [child_history]
    assert parent_map[child_in_iterator.id] == iterator.id


@pytest.mark.django_db
def test_get_node_history_result(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    node_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=workflow.get_trigger()
    )
    node_result = data_fixture.create_automation_node_result(
        node_history=node_history, result={"rows": [1, 2]}
    )

    result = AutomationHistoryService().get_node_history_result(user, node_history.id)

    assert result == node_result
    assert result.result == {"rows": [1, 2]}


@pytest.mark.django_db
def test_get_node_history_result_permission_error(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    node_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=workflow.get_trigger()
    )
    data_fixture.create_automation_node_result(node_history=node_history)

    other_user = data_fixture.create_user()

    with pytest.raises(UserNotInWorkspace):
        AutomationHistoryService().get_node_history_result(other_user, node_history.id)


@pytest.mark.django_db
def test_get_node_history_result_node_history_doesnt_exist(data_fixture):
    user = data_fixture.create_user()

    with pytest.raises(AutomationNodeHistoryDoesNotExist):
        AutomationHistoryService().get_node_history_result(user, node_history_id=999999)


@pytest.mark.django_db
def test_get_node_history_result_result_doesnt_exist(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    node_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=workflow.get_trigger()
    )

    with pytest.raises(AutomationWorkflowHistoryNodeResultDoesNotExist):
        AutomationHistoryService().get_node_history_result(user, node_history.id)
