import pytest

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
def test_get_node_histories_permission_error(data_fixture):
    user = data_fixture.create_user()
    history = data_fixture.create_workflow_history(user=user)

    user_2 = data_fixture.create_user()

    with pytest.raises(UserNotInWorkspace) as e:
        AutomationHistoryService().get_node_histories(user_2, history.id)

    assert str(e.value) == (
        f"User {user_2.email} doesn't belong to "
        f"workspace {history.workflow.automation.workspace}."
    )


@pytest.mark.django_db
def test_get_node_histories_returns_node_histories(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()
    workflow_history = data_fixture.create_automation_workflow_history(
        user=user,
        workflow=workflow,
    )

    node_history_1 = data_fixture.create_automation_node_history(
        user=user,
        workflow_history=workflow_history,
        node=trigger,
    )
    node_history_2 = data_fixture.create_automation_node_history(
        user=user,
        workflow_history=workflow_history,
        node=trigger,
    )

    result = AutomationHistoryService().get_node_histories(user, workflow_history.id)

    assert result == [node_history_1, node_history_2]


@pytest.mark.django_db
def test_get_node_history_result_permission_error(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()
    workflow_history = data_fixture.create_automation_workflow_history(
        user=user,
        workflow=workflow,
    )
    node_history = data_fixture.create_automation_node_history(
        user=user,
        workflow_history=workflow_history,
        node=trigger,
    )

    user_2 = data_fixture.create_user()

    with pytest.raises(UserNotInWorkspace) as e:
        AutomationHistoryService().get_node_history_result(user_2, node_history.id)

    assert str(e.value) == (
        f"User {user_2.email} doesn't belong to "
        f"workspace {workflow.automation.workspace}."
    )


@pytest.mark.django_db
def test_get_node_history_result_returns_result(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()
    workflow_history = data_fixture.create_automation_workflow_history(
        user=user,
        workflow=workflow,
    )
    node_history = data_fixture.create_automation_node_history(
        user=user,
        workflow_history=workflow_history,
        node=trigger,
    )
    node_result = data_fixture.create_automation_node_result(
        node_history=node_history,
        result={"foo": "bar"},
    )

    result = AutomationHistoryService().get_node_history_result(user, node_history.id)

    assert result == node_result
    assert result.result == {"foo": "bar"}


@pytest.mark.django_db
def test_get_edge_labels_returns_empty_dict(data_fixture):
    user = data_fixture.create_user()

    result = AutomationHistoryService().get_edge_labels(user, [])

    assert result == {}


@pytest.mark.django_db
def test_get_edge_labels_permission_error(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()
    workflow_history = data_fixture.create_automation_workflow_history(
        user=user,
        workflow=workflow,
    )
    node_history = data_fixture.create_automation_node_history(
        user=user,
        workflow_history=workflow_history,
        node=trigger,
    )

    user_2 = data_fixture.create_user()

    with pytest.raises(UserNotInWorkspace) as e:
        AutomationHistoryService().get_edge_labels(user_2, [node_history])

    assert str(e.value) == (
        f"User {user_2.email} doesn't belong to "
        f"workspace {workflow.automation.workspace}."
    )


@pytest.mark.django_db
def test_get_edge_labels_returns_mapping(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()
    workflow_history = data_fixture.create_automation_workflow_history(
        user=user,
        workflow=workflow,
    )

    node_history_1 = data_fixture.create_automation_node_history(
        user=user,
        workflow_history=workflow_history,
        node=trigger,
    )
    data_fixture.create_automation_node_result(
        node_history=node_history_1,
        result={"edge": {"label": "foo label"}},
    )

    node_history_2 = data_fixture.create_automation_node_history(
        user=user,
        workflow_history=workflow_history,
        node=trigger,
    )
    data_fixture.create_automation_node_result(
        node_history=node_history_2,
        result={"edge": {"label": "bar label"}},
    )

    result = AutomationHistoryService().get_edge_labels(
        user, [node_history_1, node_history_2]
    )

    assert result == {
        node_history_1.id: "foo label",
        node_history_2.id: "bar label",
    }
