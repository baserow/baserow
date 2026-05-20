from django.utils import timezone

import pytest

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.exceptions import (
    AutomationNodeHistoryDoesNotExist,
    AutomationWorkflowHistoryDoesNotExist,
    AutomationWorkflowHistoryNodeResultDoesNotExist,
)
from baserow.contrib.automation.history.handler import AutomationHistoryHandler
from baserow.contrib.automation.history.models import (
    AutomationNodeHistory,
    AutomationWorkflowHistory,
)
from baserow.contrib.automation.workflows.constants import WorkflowState


@pytest.mark.django_db
def test_get_workflow_histories_no_base_queryset(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    result = AutomationHistoryHandler().get_workflow_histories(workflow)

    # Should return an empty queryset, since this workflow has no history
    assert list(result) == []


@pytest.mark.django_db
def test_get_workflow_histories_with_base_queryset(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    result = AutomationHistoryHandler().get_workflow_histories(
        workflow, AutomationWorkflowHistory.objects.all()
    )

    # Should return an empty queryset, since this workflow has no history
    assert list(result) == []


@pytest.mark.django_db
def test_get_workflow_histories_returns_ordered_histories(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()
    history_1 = data_fixture.create_workflow_history(
        original_workflow=original_workflow
    )
    history_2 = data_fixture.create_workflow_history(
        original_workflow=original_workflow
    )

    result = AutomationHistoryHandler().get_workflow_histories(original_workflow)

    # Ensure latest is returned first
    assert list(result) == [history_2, history_1]


@pytest.mark.django_db
def test_create_workflow_history(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()
    published_workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    now = timezone.now()
    history = AutomationHistoryHandler().create_workflow_history(
        original_workflow,
        original_workflow,
        now,
        False,
    )

    assert isinstance(history, AutomationWorkflowHistory)
    assert history.workflow == original_workflow


@pytest.mark.django_db
def test_get_workflow_histories_excludes_simulation_histories(data_fixture):
    """
    Simulation histories are deleted by the dispatch_node() once the final
    node is dispatched. However, we want to ensure they're excluded so that
    a user doesn't accidentally see them while the simulation is running.
    """

    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger()

    simulation_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
        simulate_until_node=trigger,
    )

    result = AutomationHistoryHandler().get_workflow_histories(workflow)

    assert len(result) == 0


@pytest.mark.django_db
def test_get_workflow_history(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    history = AutomationHistoryHandler().create_workflow_history(
        workflow,
        workflow,
        timezone.now(),
        False,
    )

    result = AutomationHistoryHandler().get_workflow_history(history_id=history.id)

    assert result == history


@pytest.mark.django_db
def test_get_workflow_history_does_not_exist(data_fixture):
    with pytest.raises(AutomationWorkflowHistoryDoesNotExist) as e:
        AutomationHistoryHandler().get_workflow_history(history_id=100)

    assert str(e.value) == "The automation workflow history 100 does not exist."


@pytest.mark.django_db
def test_get_workflow_history_respects_base_queryset(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    history = AutomationHistoryHandler().create_workflow_history(
        workflow,
        workflow,
        timezone.now(),
        False,
    )

    with pytest.raises(AutomationWorkflowHistoryDoesNotExist) as e:
        AutomationHistoryHandler().get_workflow_history(
            history_id=history.id,
            base_queryset=AutomationWorkflowHistory.objects.exclude(id=history.id),
        )


@pytest.mark.django_db
def test_get_node_history(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    node_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history,
        node=workflow.get_trigger(),
    )

    result = AutomationHistoryHandler().get_node_history(
        node_history_id=node_history.id
    )

    assert result == node_history


@pytest.mark.django_db
def test_get_node_history_does_not_exist():
    with pytest.raises(AutomationNodeHistoryDoesNotExist) as e:
        AutomationHistoryHandler().get_node_history(node_history_id=100)

    assert str(e.value) == "The automation node history 100 does not exist."


@pytest.mark.django_db
def test_get_node_history_respects_base_queryset(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    node_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history,
        node=workflow.get_trigger(),
    )

    with pytest.raises(AutomationNodeHistoryDoesNotExist):
        AutomationHistoryHandler().get_node_history(
            node_history_id=node_history.id,
            base_queryset=AutomationNodeHistory.objects.exclude(id=node_history.id),
        )


@pytest.mark.django_db
def test_get_node_history_result(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    node_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history,
        node=workflow.get_trigger(),
    )
    node_result = data_fixture.create_automation_node_result(
        node_history=node_history,
        result={"rows": [1, 2]},
    )

    result = AutomationHistoryHandler().get_node_history_result(node_history)

    assert result == node_result
    assert result.result == {"rows": [1, 2]}


@pytest.mark.django_db
def test_get_node_history_result_does_not_exist(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    node_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history,
        node=workflow.get_trigger(),
    )

    with pytest.raises(AutomationWorkflowHistoryNodeResultDoesNotExist):
        AutomationHistoryHandler().get_node_history_result(node_history)


@pytest.mark.django_db
def test_get_child_node_histories_returns_roots_when_no_parent(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger()
    action = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
    )
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    trigger_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=trigger
    )
    action_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=action
    )

    result = AutomationHistoryHandler().get_child_node_histories(
        workflow_history=workflow_history, parent_node_id=None
    )

    assert list(result) == [trigger_history, action_history]


@pytest.mark.django_db
def test_get_child_node_histories_returns_children_of_parent(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    iterator = data_fixture.create_core_iterator_action_node(workflow=workflow)
    child_in_iterator = data_fixture.create_automation_node(
        workflow=workflow,
        reference_node=iterator,
        position="child",
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

    result = AutomationHistoryHandler().get_child_node_histories(
        workflow_history=workflow_history, parent_node_id=iterator.id
    )

    assert list(result) == [child_history]


@pytest.mark.django_db
def test_get_child_node_histories_empty_when_no_histories(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )

    result = AutomationHistoryHandler().get_child_node_histories(
        workflow_history=workflow_history, parent_node_id=None
    )

    assert list(result) == []


@pytest.mark.django_db
def test_get_child_node_histories_scoped_to_workflow_history(data_fixture):
    """
    Ensure that only node histories belonging to the workflow history is returned.
    """

    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger()

    workflow_history_1 = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    workflow_history_2 = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    history_in_1 = data_fixture.create_automation_node_history(
        workflow_history=workflow_history_1, node=trigger
    )
    data_fixture.create_automation_node_history(
        workflow_history=workflow_history_2, node=trigger
    )

    result = AutomationHistoryHandler().get_child_node_histories(
        workflow_history=workflow_history_1, parent_node_id=None
    )

    assert list(result) == [history_in_1]


@pytest.mark.django_db
def test_get_child_node_histories_filters_by_iteration_path(data_fixture):
    """
    Ensure that when an iteration_path is provided, only histories that
    starts with the iteration_path are returned.

    The frontend needs this to nest child nodes in the correct
    iteration (run).
    """

    workflow = data_fixture.create_automation_workflow()
    iterator = data_fixture.create_core_iterator_action_node(workflow=workflow)
    child_in_iterator = data_fixture.create_automation_node(
        workflow=workflow,
        reference_node=iterator,
        position="child",
    )
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )

    history_iter_0 = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=child_in_iterator
    )
    data_fixture.create_automation_node_result(
        node_history=history_iter_0,
        iteration_path="0",
    )
    history_iter_1 = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=child_in_iterator
    )
    data_fixture.create_automation_node_result(
        node_history=history_iter_1,
        iteration_path="1",
    )

    result = AutomationHistoryHandler().get_child_node_histories(
        workflow_history=workflow_history,
        parent_node_id=iterator.id,
        iteration_path="0",
    )

    assert list(result) == [history_iter_0]


@pytest.mark.django_db
def test_get_child_node_histories_ordered_by_started_on(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    trigger = workflow.get_trigger()
    action = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
    )
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )

    now = timezone.now()
    later = now + timezone.timedelta(seconds=10)
    old_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=trigger, started_on=now
    )
    new_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=action, started_on=later
    )

    result = AutomationHistoryHandler().get_child_node_histories(
        workflow_history=workflow_history, parent_node_id=None
    )

    assert list(result) == [old_history, new_history]


@pytest.mark.django_db
def test_get_router_edge_labels_no_routers(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    node_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=workflow.get_trigger()
    )
    data_fixture.create_automation_node_result(
        node_history=node_history, result={"rows": [1, 2]}
    )

    assert AutomationHistoryHandler().get_router_edge_labels([node_history]) == {}


@pytest.mark.django_db
def test_get_router_edge_labels_named_edge(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    core_router = data_fixture.create_core_router_action_node_with_edges(
        workflow=workflow,
    )
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    router_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=core_router.router
    )
    data_fixture.create_automation_node_result(
        node_history=router_history,
        result={"edge": {"label": "foo router label"}},
    )

    edge_labels = AutomationHistoryHandler().get_router_edge_labels([router_history])

    assert edge_labels == {router_history.id: "foo router label"}


@pytest.mark.django_db
def test_get_router_edge_labels_default_edge(data_fixture):
    """
    When the router falls through to the default edge, the result stores the
    configured default_edge_label. The handler surfaces it like any other.
    """

    workflow = data_fixture.create_automation_workflow()
    core_router = data_fixture.create_core_router_action_node_with_edges(
        workflow=workflow,
    )
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    router_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=core_router.router
    )
    data_fixture.create_automation_node_result(
        node_history=router_history,
        result={"edge": {"label": "Default"}},
    )

    edge_labels = AutomationHistoryHandler().get_router_edge_labels([router_history])

    assert edge_labels == {router_history.id: "Default"}


@pytest.mark.django_db
def test_get_router_edge_labels_omits_empty_label(data_fixture):
    """
    If the edge label is an empty string, ensure that it's omitted. The
    frontend will then use the i18n default router label fallback.
    """

    workflow = data_fixture.create_automation_workflow()
    core_router = data_fixture.create_core_router_action_node_with_edges(
        workflow=workflow,
    )
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    router_history = data_fixture.create_automation_node_history(
        workflow_history=workflow_history, node=core_router.router
    )
    data_fixture.create_automation_node_result(
        node_history=router_history, result={"edge": {"label": ""}}
    )

    edge_labels = AutomationHistoryHandler().get_router_edge_labels([router_history])

    assert edge_labels == {}


@pytest.mark.django_db
def test_get_error_ancestor_node_ids_no_errors(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    data_fixture.create_automation_node_history(
        workflow_history=workflow_history,
        node=workflow.get_trigger(),
        status=HistoryStatusChoices.SUCCESS,
    )

    ancestors = AutomationHistoryHandler().get_error_ancestor_node_ids(workflow_history)

    assert ancestors == set()


@pytest.mark.django_db
def test_get_error_ancestor_node_ids_error(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    iterator = data_fixture.create_core_iterator_action_node(workflow=workflow)
    child_in_iterator = data_fixture.create_automation_node(
        workflow=workflow,
        reference_node=iterator,
        position="child",
    )
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    data_fixture.create_automation_node_history(
        workflow_history=workflow_history,
        node=child_in_iterator,
        status=HistoryStatusChoices.ERROR,
    )

    ancestors = AutomationHistoryHandler().get_error_ancestor_node_ids(workflow_history)

    assert ancestors == {iterator.id}


@pytest.mark.django_db
def test_get_error_ancestor_node_ids_errored_in_nested_iterators(data_fixture):
    """
    Ensure that when a deeply nested node has an error, all parent container
    node IDs are returned.
    """

    workflow = data_fixture.create_automation_workflow()
    outer_iterator = data_fixture.create_core_iterator_action_node(workflow=workflow)
    inner_iterator = data_fixture.create_core_iterator_action_node(
        workflow=workflow, reference_node=outer_iterator, position="child"
    )
    action_node = data_fixture.create_automation_node(
        workflow=workflow, reference_node=inner_iterator, position="child"
    )
    workflow_history = data_fixture.create_automation_workflow_history(
        workflow=workflow,
    )
    data_fixture.create_automation_node_history(
        workflow_history=workflow_history,
        node=action_node,
        status=HistoryStatusChoices.ERROR,
    )

    ancestors = AutomationHistoryHandler().get_error_ancestor_node_ids(workflow_history)

    assert ancestors == {outer_iterator.id, inner_iterator.id}
