from unittest.mock import patch

import pytest

from baserow.contrib.automation.history.models import AutomationWorkflowHistory
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.automation.workflows.exceptions import (
    AutomationWorkflowBeforeRunError,
    AutomationWorkflowTooManyErrors,
)
from baserow.contrib.automation.workflows.tasks import start_workflow_celery_task


@pytest.mark.django_db
@patch(
    "baserow.contrib.automation.workflows.handler.AutomationWorkflowHandler._check_too_many_errors"
)
@patch("baserow.contrib.automation.nodes.tasks.dispatch_node_celery_task")
def test_run_workflow_disables_workflow_if_too_many_consecutive_errors(
    mock_dispatch_task, mock_has_too_many_errors, data_fixture
):
    mock_has_too_many_errors.side_effect = AutomationWorkflowTooManyErrors(
        "mock too many errors"
    )

    original_workflow = data_fixture.create_automation_workflow()
    published_workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    start_workflow_celery_task(published_workflow.id, None, None)

    # Nodes shouldn't be dispatched because before_run() should return early.
    mock_dispatch_task.delay.assert_not_called()

    histories = AutomationWorkflowHistory.objects.filter(workflow=original_workflow)

    assert len(histories) == 1

    history = histories[0]
    assert history.workflow == original_workflow
    assert history.status == "disabled"

    error_msg = "mock too many errors"
    assert history.message == error_msg

    original_workflow.refresh_from_db()
    published_workflow.refresh_from_db()

    assert original_workflow.state == WorkflowState.DISABLED
    assert published_workflow.state == WorkflowState.DISABLED


@pytest.mark.django_db
@patch(
    "baserow.contrib.automation.workflows.handler.AutomationWorkflowHandler.before_run"
)
@patch("baserow.contrib.automation.nodes.tasks.dispatch_node_celery_task")
def test_start_workflow_before_run_error_creates_error_history(
    mock_dispatch_task, mock_before_run, data_fixture
):
    # We already test the specific AutomationWorkflowTooManyErrors error above,
    # but we should also test that before_run() has error handling.
    mock_before_run.side_effect = AutomationWorkflowBeforeRunError("unexpected error")

    original_workflow = data_fixture.create_automation_workflow()
    published_workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    start_workflow_celery_task(published_workflow.id, None, None)

    mock_dispatch_task.delay.assert_not_called()

    history = AutomationWorkflowHistory.objects.get(workflow=original_workflow)
    assert history.status == "error"
    assert history.message == "unexpected error"
