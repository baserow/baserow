import pytest


@pytest.mark.django_db
def test_automation_workflow_get_parent(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)

    result = workflow.get_parent()

    assert result == workflow.automation
