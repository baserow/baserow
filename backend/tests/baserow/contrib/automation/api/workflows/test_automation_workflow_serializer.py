import pytest

from baserow.contrib.automation.api.workflows.serializers import (
    AutomationWorkflowSerializer,
    CreateAutomationWorkflowSerializer,
    UpdateAutomationWorkflowSerializer,
)


@pytest.fixture()
def workflow_fixture(data_fixture):
    """A helper to test the AutomationWorkflowSerializer."""

    user, _ = data_fixture.create_user_and_token()
    automation = data_fixture.create_automation_application(user=user)
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name="test"
    )

    return {
        "automation": automation,
        "user": user,
        "workflow": workflow,
    }


@pytest.mark.django_db
def test_automation_workflow_serializer_fields(workflow_fixture):
    workflow = workflow_fixture["workflow"]

    serializer = AutomationWorkflowSerializer(instance=workflow)

    assert sorted(serializer.data.keys()) == [
        "allow_test_run_until",
        "automation_id",
        "graph",
        "id",
        "name",
        "order",
        "published_on",
        "simulate_until_node_id",
        "state",
    ]


@pytest.mark.django_db
def test_create_automation_workflow_serializer_fields(workflow_fixture):
    workflow = workflow_fixture["workflow"]

    serializer = CreateAutomationWorkflowSerializer(instance=workflow)

    assert sorted(serializer.data.keys()) == ["name"]


@pytest.mark.django_db
def test_update_automation_workflow_serializer_fields(workflow_fixture):
    workflow = workflow_fixture["workflow"]

    serializer = UpdateAutomationWorkflowSerializer(instance=workflow)

    assert sorted(serializer.data.keys()) == ["name", "state"]
