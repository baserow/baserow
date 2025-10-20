import pytest

from baserow.contrib.automation.api.serializers import AutomationSerializer


@pytest.fixture()
def automation_fixture(data_fixture):
    """A helper to test the AutomationSerializer."""

    user, _ = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        workspace=workspace,
        order=1,
    )
    workflow = data_fixture.create_automation_workflow(
        user, automation=automation, name="test"
    )

    return {
        "automation": automation,
        "user": user,
        "workflow": workflow,
    }


@pytest.mark.django_db
def test_serializer_has_expected_fields(automation_fixture):
    automation = automation_fixture["automation"]

    serializer = AutomationSerializer(instance=automation)

    assert sorted(serializer.data.keys()) == [
        "id",
        "name",
        "workflows",
    ]


@pytest.mark.django_db
def test_serializer_get_workflows(automation_fixture):
    automation = automation_fixture["automation"]
    workflow = automation_fixture["workflow"]
    trigger = workflow.get_trigger()

    serializer = AutomationSerializer(instance=automation)

    workflows = serializer.get_workflows(automation)
    assert workflows == [
        {
            "id": workflow.id,
            "name": "test",
            "order": 1,
            "automation_id": automation.id,
            "allow_test_run_until": None,
            "state": "draft",
            "simulate_until_node_id": None,
            "published_on": None,
            "graph": {"0": trigger.id, str(trigger.id): {}},
        }
    ]
