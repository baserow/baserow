from django.utils import timezone

import pytest

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
    user, _ = data_fixture.create_user_and_token()
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
    user, _ = data_fixture.create_user_and_token()
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

    with pytest.raises(AutomationNodeHistoryDoesNotExist):
        AutomationHistoryHandler().get_node_history(
            node_history_id=node_history.id,
            base_queryset=AutomationNodeHistory.objects.exclude(id=node_history.id),
        )


@pytest.mark.django_db
def test_get_node_histories_returns_empty_when_no_histories(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    workflow_history = data_fixture.create_automation_workflow_history(
        user=user,
        workflow=workflow,
    )

    result = AutomationHistoryHandler().get_node_histories(workflow_history)

    assert list(result) == []


@pytest.mark.django_db
def test_get_node_histories_filters_by_workflow_history(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()
    workflow_history = data_fixture.create_automation_workflow_history(
        user=user,
        workflow=workflow,
    )
    other_workflow_history = data_fixture.create_automation_workflow_history(
        user=user,
        workflow=workflow,
    )

    node_history = data_fixture.create_automation_node_history(
        user=user,
        workflow_history=workflow_history,
        node=trigger,
    )
    data_fixture.create_automation_node_history(
        user=user,
        workflow_history=other_workflow_history,
        node=trigger,
    )

    result = AutomationHistoryHandler().get_node_histories(workflow_history)

    assert list(result) == [node_history]


@pytest.mark.django_db
def test_get_node_histories_ordering(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()
    workflow_history = data_fixture.create_automation_workflow_history(
        user=user,
        workflow=workflow,
    )

    earlier = timezone.now()
    later = earlier + timezone.timedelta(seconds=10)

    node_history_2 = data_fixture.create_automation_node_history(
        user=user,
        workflow_history=workflow_history,
        node=trigger,
        started_on=later,
    )
    node_history_1 = data_fixture.create_automation_node_history(
        user=user,
        workflow_history=workflow_history,
        node=trigger,
        started_on=earlier,
    )
    node_history_3 = data_fixture.create_automation_node_history(
        user=user,
        workflow_history=workflow_history,
        node=trigger,
        started_on=later,
    )

    result = AutomationHistoryHandler().get_node_histories(workflow_history)

    assert list(result) == [node_history_1, node_history_2, node_history_3]


@pytest.mark.django_db
def test_get_node_histories_prefetches_node_results(
    data_fixture, django_assert_num_queries
):
    user, _ = data_fixture.create_user_and_token()
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
    )

    result = list(AutomationHistoryHandler().get_node_histories(workflow_history))

    with django_assert_num_queries(0):
        result = list(result[0].node_results.all())

    assert result == [node_result]


@pytest.mark.django_db
def test_get_node_history_result(data_fixture):
    user, _ = data_fixture.create_user_and_token()
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

    result = AutomationHistoryHandler().get_node_history_result(node_history)

    assert result == node_result
    assert result.result == {"foo": "bar"}


@pytest.mark.django_db
def test_get_node_result_returns_latest_pass_when_node_loops(data_fixture):
    """
    When a node is dispatched multiple times in a single run (e.g. a "Go to node"
    jump loops back to it), several results share the same iteration_path. Reading
    the previous result should return the most recent pass rather than raising
    MultipleObjectsReturned.
    """

    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()
    workflow_history = data_fixture.create_automation_workflow_history(
        user=user,
        workflow=workflow,
    )

    earlier = timezone.now()
    later = earlier + timezone.timedelta(seconds=10)

    first_history = data_fixture.create_automation_node_history(
        user=user,
        workflow_history=workflow_history,
        node=trigger,
        started_on=earlier,
    )
    data_fixture.create_automation_node_result(
        node_history=first_history,
        iteration_path="",
        result={"pass": 1},
    )

    latest_history = data_fixture.create_automation_node_history(
        user=user,
        workflow_history=workflow_history,
        node=trigger,
        started_on=later,
    )
    data_fixture.create_automation_node_result(
        node_history=latest_history,
        iteration_path="",
        result={"pass": 2},
    )

    result = AutomationHistoryHandler().get_node_result(workflow_history, trigger, "")

    assert result == {"pass": 2}


@pytest.mark.django_db
def test_get_goto_destination_labels(data_fixture):
    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()
    destination = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, reference_node=trigger, label="destination node"
    )
    goto_node = data_fixture.create_core_goto_node(
        workflow=workflow, reference_node=destination
    )
    goto_node.service.specific.destination_node = destination
    goto_node.service.specific.save()

    workflow_history = data_fixture.create_automation_workflow_history(
        user=user, workflow=workflow
    )
    goto_history = data_fixture.create_automation_node_history(
        user=user, workflow_history=workflow_history, node=goto_node
    )
    # A non-goto entry should be ignored.
    trigger_history = data_fixture.create_automation_node_history(
        user=user, workflow_history=workflow_history, node=trigger
    )

    labels = AutomationHistoryHandler().get_goto_destination_labels(
        [goto_history, trigger_history]
    )

    assert labels == {
        goto_history.id: {
            "id": destination.id,
            "type": destination.get_type().type,
            "label": "destination node",
        }
    }


@pytest.mark.django_db
def test_get_goto_destination_labels_without_custom_label(data_fixture):
    """
    When the destination node has no custom label, the returned label is empty but
    the node type is still provided so the frontend can show a generic name.
    """

    user, _ = data_fixture.create_user_and_token()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()
    destination = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, reference_node=trigger
    )
    goto_node = data_fixture.create_core_goto_node(
        workflow=workflow, reference_node=destination
    )
    goto_node.service.specific.destination_node = destination
    goto_node.service.specific.save()

    workflow_history = data_fixture.create_automation_workflow_history(
        user=user, workflow=workflow
    )
    goto_history = data_fixture.create_automation_node_history(
        user=user, workflow_history=workflow_history, node=goto_node
    )

    labels = AutomationHistoryHandler().get_goto_destination_labels([goto_history])

    assert destination.label == ""
    assert labels == {
        goto_history.id: {
            "id": destination.id,
            "type": destination.get_type().type,
            "label": "",
        }
    }


@pytest.mark.django_db
def test_get_node_history_result_does_not_exist(data_fixture):
    user, _ = data_fixture.create_user_and_token()
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

    with pytest.raises(AutomationWorkflowHistoryNodeResultDoesNotExist):
        AutomationHistoryHandler().get_node_history_result(node_history)


@pytest.mark.django_db
def test_get_edge_labels_returns_empty_dict():
    assert AutomationHistoryHandler().get_edge_labels([]) == {}


@pytest.mark.django_db
def test_get_edge_labels_returns_expected_data(data_fixture):
    user, _ = data_fixture.create_user_and_token()
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

    result = AutomationHistoryHandler().get_edge_labels(
        [node_history_1, node_history_2]
    )

    assert result == {
        node_history_1.id: "foo label",
        node_history_2.id: "bar label",
    }
