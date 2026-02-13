from baserow.contrib.automation.history.models import AutomationWorkflowHistory


def assert_history(workflow, expected_count, expected_status, expected_msg):
    """Helper to test AutomationWorkflowHistory objects."""

    histories = AutomationWorkflowHistory.objects.filter(workflow=workflow)
    assert len(histories) == expected_count
    if expected_count > 0:
        history = histories[0]
        assert history.workflow == workflow
        assert history.status == expected_status
        assert history.message == expected_msg
