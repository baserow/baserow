from baserow.contrib.automation.history.models import AutomationWorkflowHistory


def assert_history(
    workflow, expected_count, expected_status, expected_msg, history_index=-1
):
    """Helper to test AutomationWorkflowHistory objects."""

    histories = list(
        AutomationWorkflowHistory.objects.filter(workflow=workflow).order_by(
            "started_on", "id"
        )
    )
    assert len(histories) == expected_count
    if expected_count > 0:
        history = histories[history_index]
        assert history.workflow == workflow
        assert history.status == expected_status
        assert history.message == expected_msg
