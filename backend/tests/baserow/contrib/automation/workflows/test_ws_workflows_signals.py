from unittest.mock import patch

import pytest

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.service import AutomationHistoryService
from baserow.contrib.automation.workflows.object_scopes import (
    AutomationWorkflowObjectScopeType,
)
from baserow.contrib.automation.workflows.operations import (
    ReadAutomationWorkflowOperationType,
)

WS_SIGNALS_PATH = "baserow.contrib.automation.workflows.ws.signals"


@pytest.mark.django_db(transaction=True)
@patch(f"{WS_SIGNALS_PATH}.broadcast_to_permitted_users")
def test_workflow_dispatch_cancellation_requested(mock_broadcast, data_fixture):
    user = data_fixture.create_user()
    user.web_socket_id = "requester-socket"
    # Runs execute against the published clone, the broadcast targets the users
    # of the editable original workflow.
    original_workflow = data_fixture.create_automation_workflow(user=user)
    published_workflow = data_fixture.create_automation_workflow(
        automation=original_workflow.automation
    )
    history = data_fixture.create_automation_workflow_history(
        workflow=published_workflow,
        original_workflow=original_workflow,
        status=HistoryStatusChoices.STARTED,
    )

    AutomationHistoryService().request_cancellation(user, history.id)

    mock_broadcast.delay.assert_called_once_with(
        original_workflow.automation.workspace_id,
        ReadAutomationWorkflowOperationType.type,
        AutomationWorkflowObjectScopeType.type,
        original_workflow.id,
        {
            "type": "automation_workflow_dispatch_cancellation_requested",
            "workflow_id": original_workflow.id,
            "history_id": history.id,
        },
        "requester-socket",
    )
