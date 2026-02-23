from django.utils import timezone

import pytest

from baserow.contrib.automation.history.handler import AutomationHistoryHandler
from baserow.contrib.automation.history.models import AutomationWorkflowHistory
from baserow.contrib.automation.workflows.constants import WorkflowState


@pytest.mark.django_db
def test_get_workflow_history_no_base_queryset(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    result = AutomationHistoryHandler().get_workflow_history(workflow)

    # Should return an empty queryset, since this workflow has no history
    assert list(result) == []


@pytest.mark.django_db
def test_get_workflow_history_with_base_queryset(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    result = AutomationHistoryHandler().get_workflow_history(
        workflow, AutomationWorkflowHistory.objects.all()
    )

    # Should return an empty queryset, since this workflow has no history
    assert list(result) == []


@pytest.mark.django_db
def test_get_workflow_history_returns_ordered_histories(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()
    history_1 = data_fixture.create_workflow_history(
        original_workflow=original_workflow
    )
    history_2 = data_fixture.create_workflow_history(
        original_workflow=original_workflow
    )

    result = AutomationHistoryHandler().get_workflow_history(original_workflow)

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
        now,
        False,
    )

    assert isinstance(history, AutomationWorkflowHistory)
    assert history.workflow == original_workflow


@pytest.mark.django_db
def test_get_workflow_history_excludes_simulation_histories(data_fixture):
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

    result = AutomationHistoryHandler().get_workflow_history(workflow)

    assert len(result) == 0
