from unittest.mock import patch

from django.test import override_settings

import pytest

from baserow.contrib.automation.history.models import AutomationWorkflowHistory
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.automation.workflows.exceptions import (
    AutomationWorkflowRateLimited,
    AutomationWorkflowTooManyErrors,
)
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.automation.workflows.tasks import start_workflow_celery_task
from baserow.core.services.exceptions import DispatchException


@pytest.mark.django_db
@patch("baserow.contrib.automation.nodes.handler.AutomationNodeHandler.dispatch_node")
def test_run_workflow_success_creates_workflow_history(
    mock_dispatch_node, data_fixture
):
    user = data_fixture.create_user()
    original_workflow = data_fixture.create_automation_workflow(user)
    published_workflow = data_fixture.create_automation_workflow(
        user, state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    assert (
        AutomationWorkflowHistory.objects.filter(workflow=original_workflow).count()
        == 0
    )

    AutomationWorkflowHandler().start_workflow(published_workflow, {"event": "payload"})

    histories = AutomationWorkflowHistory.objects.filter(workflow=original_workflow)
    assert len(histories) == 1
    history = histories[0]
    assert history.workflow == original_workflow
    assert history.status == "success"
    assert history.message == ""


@pytest.mark.django_db
@patch("baserow.contrib.automation.nodes.handler.AutomationNodeHandler.dispatch_node")
def test_run_workflow_dispatch_error_creates_workflow_history(
    mock_dispatch_node, data_fixture
):
    original_workflow = data_fixture.create_automation_workflow()
    published_workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    mock_dispatch_node.side_effect = DispatchException("mock dispatch error")

    assert (
        AutomationWorkflowHistory.objects.filter(workflow=original_workflow).count()
        == 0
    )

    result = start_workflow_celery_task(published_workflow.id, False, None)

    assert result is None
    histories = AutomationWorkflowHistory.objects.filter(workflow=original_workflow)
    assert len(histories) == 1
    history = histories[0]
    assert history.workflow == original_workflow
    assert history.status == "error"
    assert history.message == "mock dispatch error"


@pytest.mark.django_db
@patch("baserow.contrib.automation.nodes.handler.AutomationNodeHandler.dispatch_node")
@patch("baserow.contrib.automation.workflows.handler.logger")
def test_run_workflow_unexpected_error_creates_workflow_history(
    mock_logger, mock_dispatch_node, data_fixture
):
    original_workflow = data_fixture.create_automation_workflow()
    published_workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    mock_dispatch_node.side_effect = ValueError("mock unexpected error")

    assert (
        AutomationWorkflowHistory.objects.filter(workflow=original_workflow).count()
        == 0
    )

    result = start_workflow_celery_task(published_workflow.id, False, None)

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


def assert_history(workflow, expected_count, expected_status, expected_msg):
    histories = AutomationWorkflowHistory.objects.filter(workflow=workflow)
    assert len(histories) == expected_count
    history = histories[0]
    assert history.workflow == workflow
    assert history.status == expected_status
    assert history.message == expected_msg


@pytest.mark.django_db
@override_settings(
    AUTOMATION_WORKFLOW_MAX_CONSECUTIVE_ERRORS=3,
    AUTOMATION_WORKFLOW_RATE_LIMIT_MAX_RUNS=10,
)
@patch(
    "baserow.contrib.automation.workflows.handler.AutomationWorkflowHandler._check_is_rate_limited"
)
@patch("baserow.contrib.automation.nodes.handler.AutomationNodeHandler.dispatch_node")
def test_run_workflow_disables_workflow_if_too_many_errors(
    mock_dispatch_node, mock_is_rate_limited, data_fixture
):
    mock_is_rate_limited.side_effect = AutomationWorkflowRateLimited(
        "mock rate limited error"
    )

    original_workflow = data_fixture.create_automation_workflow()
    published_workflow = data_fixture.create_automation_workflow(
        state=WorkflowState.LIVE
    )
    published_workflow.automation.published_from = original_workflow
    published_workflow.automation.save()

    # The first 3 runs should just be an error
    for i in range(3):
        start_workflow_celery_task(published_workflow.id, False, None)
        mock_dispatch_node.assert_not_called()
        assert_history(original_workflow, i + 1, "error", "mock rate limited error")
        original_workflow.refresh_from_db()
        published_workflow.refresh_from_db()
        assert original_workflow.state == WorkflowState.DRAFT
        assert published_workflow.state == WorkflowState.LIVE

    # The fourth run should disable the workflow due to too many errors
    start_workflow_celery_task(published_workflow.id, False, None)
    mock_dispatch_node.assert_not_called()
    assert_history(
        original_workflow,
        4,
        "disabled",
        f"The workflow {original_workflow.id} was disabled due to too many consecutive errors.",
    )
    original_workflow.refresh_from_db()
    published_workflow.refresh_from_db()
    assert original_workflow.state == WorkflowState.DISABLED
    assert published_workflow.state == WorkflowState.DISABLED


@pytest.mark.django_db
@patch(
    "baserow.contrib.automation.workflows.handler.AutomationWorkflowHandler._check_too_many_errors"
)
@patch("baserow.contrib.automation.nodes.handler.AutomationNodeHandler.dispatch_node")
def test_run_workflow_disables_workflow_if_too_many_consecutive_errors(
    mock_dispatch_node, mock_has_too_many_errors, data_fixture
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

    start_workflow_celery_task(published_workflow.id, False, None)

    mock_dispatch_node.assert_not_called()

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
