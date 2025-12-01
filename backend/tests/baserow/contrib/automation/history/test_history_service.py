import pytest

from baserow.contrib.automation.history.service import AutomationHistoryService
from baserow.core.exceptions import UserNotInWorkspace


@pytest.mark.django_db
def test_get_workflow_history_permission_error(data_fixture):
    user = data_fixture.create_user()
    history = data_fixture.create_workflow_history(user=user)

    # Different user
    user_2 = data_fixture.create_user()

    with pytest.raises(UserNotInWorkspace) as e:
        AutomationHistoryService().get_workflow_history(user_2, history.workflow.id)

    assert str(e.value) == (
        f"User {user_2.email} doesn't belong to "
        f"workspace {history.workflow.automation.workspace}."
    )


@pytest.mark.django_db
def test_get_workflow_history_returns_ordered_histories(data_fixture):
    user = data_fixture.create_user()
    original_workflow = data_fixture.create_automation_workflow(user=user)

    history_1 = data_fixture.create_workflow_history(
        original_workflow=original_workflow
    )
    history_2 = data_fixture.create_workflow_history(
        original_workflow=original_workflow
    )

    result = AutomationHistoryService().get_workflow_history(user, original_workflow.id)

    assert list(result) == [history_2, history_1]
