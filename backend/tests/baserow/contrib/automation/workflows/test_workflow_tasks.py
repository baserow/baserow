from unittest.mock import patch

from django.test import override_settings

import pytest
from freezegun import freeze_time

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.automation.workflows.tasks import clear_old_automation_history


@override_settings(AUTOMATION_WORKFLOW_HISTORY_MAX_DAYS=7)
@pytest.mark.django_db
def test_old_automation_history_entries_are_deleted(data_fixture):
    workflow_a = data_fixture.create_automation_workflow()
    workflow_b = data_fixture.create_automation_workflow()

    with freeze_time("2026-04-10 12:00:00"):
        recent_history = data_fixture.create_automation_workflow_history(
            workflow=workflow_a, status=HistoryStatusChoices.SUCCESS
        )

    with freeze_time("2026-04-02 12:00:00"):
        old_history_1 = data_fixture.create_automation_workflow_history(
            workflow=workflow_a, status=HistoryStatusChoices.SUCCESS
        )
        old_history_2 = data_fixture.create_automation_workflow_history(
            workflow=workflow_b, status=HistoryStatusChoices.SUCCESS
        )

    with freeze_time("2026-04-10 12:00:00"):
        clear_old_automation_history()

    assert not workflow_a.workflow_histories.filter(id=old_history_1.id).exists()
    assert not workflow_b.workflow_histories.filter(id=old_history_2.id).exists()
    assert workflow_a.workflow_histories.filter(id=recent_history.id).exists()


@override_settings(AUTOMATION_WORKFLOW_HISTORY_MAX_DAYS=7)
@pytest.mark.django_db
def test_clear_old_automation_history_continues_on_error(data_fixture):
    workflow_a = data_fixture.create_automation_workflow()
    workflow_b = data_fixture.create_automation_workflow()

    with freeze_time("2026-04-02 12:00:00"):
        old_history_a = data_fixture.create_automation_workflow_history(
            workflow=workflow_a, status=HistoryStatusChoices.SUCCESS
        )
        old_history_b = data_fixture.create_automation_workflow_history(
            workflow=workflow_b, status=HistoryStatusChoices.SUCCESS
        )

    original_method = AutomationWorkflowHandler._clear_old_history

    def side_effect(self, workflow):
        """Simulate an error when trying to clean-up workflow_a."""
        if workflow.id == workflow_a.id:
            raise Exception("unexpected error")
        return original_method(self, workflow)

    with patch.object(
        AutomationWorkflowHandler,
        "_clear_old_history",
        side_effect=side_effect,
        autospec=True,
    ):
        with freeze_time("2026-04-10 12:00:00"):
            clear_old_automation_history()

    # Although workflow_a ran into an error, workflow_b should still
    # be cleaned up.
    assert workflow_a.workflow_histories.filter(id=old_history_a.id).exists()
    assert not workflow_b.workflow_histories.filter(id=old_history_b.id).exists()
