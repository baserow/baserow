from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK


@pytest.mark.django_db
def test_get_automation_application(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@baserow.io", password="password", first_name="TestFirstName"
    )
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        workspace=workspace,
        order=1,
    )
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name="test"
    )
    trigger = workflow.get_trigger()

    url = reverse("api:applications:item", kwargs={"application_id": automation.id})

    response = api_client.get(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json == {
        "id": automation.id,
        "name": automation.name,
        "order": automation.order,
        "created_on": automation.created_on.isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        ),
        "type": "automation",
        "workspace": {
            "id": workspace.id,
            "name": workspace.name,
            "generative_ai_models_enabled": {},
        },
        "workflows": [
            {
                "automation_id": automation.id,
                "id": workflow.id,
                "name": "test",
                "order": 1,
                "allow_test_run_until": None,
                "simulate_until_node_id": None,
                "state": "draft",
                "published_on": None,
                "graph": {"0": trigger.id, str(trigger.id): {}},
            }
        ],
    }


@pytest.mark.django_db
def test_list_automation_applications(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(
        workspace=workspace,
        order=1,
    )
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name="test"
    )
    trigger = workflow.get_trigger()

    url = reverse("api:applications:list", kwargs={"workspace_id": workspace.id})

    response = api_client.get(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json == [
        {
            "created_on": automation.created_on.isoformat(
                timespec="microseconds"
            ).replace("+00:00", "Z"),
            "id": automation.id,
            "name": automation.name,
            "order": automation.order,
            "type": "automation",
            "workspace": {
                "id": workspace.id,
                "name": workspace.name,
                "generative_ai_models_enabled": {},
            },
            "workflows": [
                {
                    "automation_id": automation.id,
                    "id": workflow.id,
                    "name": "test",
                    "order": 1,
                    "allow_test_run_until": None,
                    "simulate_until_node_id": None,
                    "state": "draft",
                    "published_on": None,
                    "graph": {"0": trigger.id, str(trigger.id): {}},
                }
            ],
        }
    ]
