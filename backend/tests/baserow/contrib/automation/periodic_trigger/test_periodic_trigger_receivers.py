from unittest.mock import patch

from django.utils import timezone

import pytest

from baserow.contrib.automation.nodes.periodic_trigger.models import (
    PERIODIC_INTERVAL_MINUTE,
)
from baserow.contrib.automation.workflows.signals import automation_workflow_updated


@pytest.mark.django_db
@patch("baserow.contrib.automation.workflows.runner.AutomationWorkflowRunner.run")
def test_periodic_trigger_receiver_with_allow_test_run_until(
    mock_runner_run, data_fixture
):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation,
        published=False,
        paused=True,
        allow_test_run_until=timezone.now() + timezone.timedelta(hours=1),
    )
    trigger_node = data_fixture.create_periodic_trigger_node(
        workflow=workflow,
        service_kwargs={
            "interval": PERIODIC_INTERVAL_MINUTE,
        },
    )

    automation_workflow_updated.send(
        sender=None,
        workflow=workflow,
        user=user,
    )

    mock_runner_run.assert_called_once()
    args = mock_runner_run.call_args[0]
    assert args[0] == workflow
    dispatch_context = args[1]
    assert dispatch_context.workflow == workflow

    workflow.refresh_from_db()
    assert workflow.allow_test_run_until is None
