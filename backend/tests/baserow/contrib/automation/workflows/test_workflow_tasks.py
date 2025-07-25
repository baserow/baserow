from unittest.mock import patch

import pytest

from baserow.contrib.automation.history.models import AutomationWorkflowHistory
from baserow.contrib.automation.workflows.tasks import run_workflow
from baserow.core.services.exceptions import DispatchException


@pytest.mark.django_db
def test_run_workflow_success_creates_workflow_history(data_fixture):
    original_workflow = data_fixture.create_automation_workflow()
    published_workflow = data_fixture.create_automation_workflow(published=True)
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()
    data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=published_workflow
    )

    assert (
        AutomationWorkflowHistory.objects.filter(workflow=original_workflow).count()
        == 0
    )

    result = run_workflow(published_workflow.id, False, None)

    assert result is None
    histories = AutomationWorkflowHistory.objects.filter(workflow=original_workflow)
    assert len(histories) == 1
    history = histories[0]
    assert history.workflow == original_workflow
    assert history.status == "success"
    assert history.message == ""


@pytest.mark.django_db
@patch("baserow.contrib.automation.workflows.tasks.AutomationWorkflowRunner.run")
def test_run_workflow_dispatch_error_creates_workflow_history(mock_run, data_fixture):
    original_workflow = data_fixture.create_automation_workflow()
    published_workflow = data_fixture.create_automation_workflow(published=True)
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()
    data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=published_workflow
    )

    mock_run.side_effect = DispatchException("mock dispatch error")

    assert (
        AutomationWorkflowHistory.objects.filter(workflow=original_workflow).count()
        == 0
    )

    result = run_workflow(published_workflow.id, False, None)

    assert result is None
    histories = AutomationWorkflowHistory.objects.filter(workflow=original_workflow)
    assert len(histories) == 1
    history = histories[0]
    assert history.workflow == original_workflow
    assert history.status == "error"
    assert history.message == "mock dispatch error"


@pytest.mark.django_db
@patch("baserow.contrib.automation.workflows.tasks.AutomationWorkflowRunner.run")
@patch("baserow.contrib.automation.workflows.tasks.logger")
def test_run_workflow_unexpected_error_creates_workflow_history(
    mock_logger, mock_run, data_fixture
):
    original_workflow = data_fixture.create_automation_workflow()
    published_workflow = data_fixture.create_automation_workflow(published=True)
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()
    data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=published_workflow
    )

    mock_run.side_effect = ValueError("mock unexpected error")

    assert (
        AutomationWorkflowHistory.objects.filter(workflow=original_workflow).count()
        == 0
    )

    result = run_workflow(published_workflow.id, False, None)

    assert result is None

    histories = AutomationWorkflowHistory.objects.filter(workflow=original_workflow)
    assert len(histories) == 1
    history = histories[0]
    assert history.workflow == original_workflow
    assert history.status == "error"
    error_msg = (
        f"Unexpected error while running workflow {original_workflow.id}. "
        "Error: mock unexpected error"
    )
    assert history.message == error_msg
    mock_logger.exception.assert_called_once_with(error_msg)
