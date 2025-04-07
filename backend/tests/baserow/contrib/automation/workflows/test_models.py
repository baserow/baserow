import pytest

from baserow.contrib.automation.workflows.registries import (
    automation_workflow_type_registry,
)


@pytest.mark.django_db
def test_automation_workflow_get_parent(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)

    result = workflow.get_parent()

    assert result == workflow.automation


@pytest.mark.django_db
def test_automation_workflow_get_type_registry(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)

    result = workflow.get_type_registry()

    assert result == automation_workflow_type_registry
