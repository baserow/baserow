from unittest.mock import MagicMock, patch

from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.core.user_templates.tasks import delete_orphaned_user_template_workspaces


def test_cleanup_task_removes_templates_before_the_sweep():
    calls = MagicMock()

    with (
        patch.object(
            UserTemplateHandler,
            "delete_marked_templates",
            calls.delete_marked_templates,
        ),
        patch.object(
            UserTemplateHandler,
            "delete_content_of_unfinished_jobs",
            calls.delete_content_of_unfinished_jobs,
        ),
    ):
        delete_orphaned_user_template_workspaces()

    assert [call[0] for call in calls.mock_calls] == [
        "delete_marked_templates",
        "delete_content_of_unfinished_jobs",
    ]
