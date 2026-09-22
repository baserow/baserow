from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_403_FORBIDDEN

from baserow.core.agents.subjects import AgentSubjectType
from baserow.core.models import Agent
from baserow.core.subjects import UserSubjectType


@pytest.mark.django_db
def test_staff_can_search_global_subject_options(api_client, data_fixture):
    staff, token = data_fixture.create_user_and_token(
        email="staff@example.com", is_staff=True
    )
    matching_user = data_fixture.create_user(email="matching@example.com")
    data_fixture.create_user(email="other@example.com")
    workspace = data_fixture.create_workspace(user=staff)
    matching_agent = Agent.objects.create(workspace=workspace, name="Matching robot")

    response = api_client.get(
        reverse("api:subjects:list"),
        {
            "search": "matching",
            "subject_types": f"{UserSubjectType.type},{AgentSubjectType.type}",
        },
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["results"] == [
        {
            "id": f"{UserSubjectType.type}:{matching_user.id}",
            "subject_id": matching_user.id,
            "subject_type": UserSubjectType.type,
            "name": matching_user.first_name,
            "label": matching_user.email,
            "email": matching_user.email,
            "subject_count": None,
        },
        {
            "id": f"{AgentSubjectType.type}:{matching_agent.id}",
            "subject_id": matching_agent.id,
            "subject_type": AgentSubjectType.type,
            "name": matching_agent.name,
            "label": matching_agent.name,
            "email": None,
            "subject_count": None,
        },
    ]


@pytest.mark.django_db
def test_non_staff_cannot_list_global_subject_options(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()

    response = api_client.get(
        reverse("api:subjects:list"), HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_workspace_subject_options_are_scoped(api_client, data_fixture):
    admin, token = data_fixture.create_user_and_token(email="admin@example.com")
    workspace = data_fixture.create_workspace(user=admin)
    agent = Agent.objects.create(workspace=workspace, name="Workspace robot")
    other_workspace = data_fixture.create_workspace()
    Agent.objects.create(workspace=other_workspace, name="Other robot")

    response = api_client.get(
        reverse("api:subjects:list"),
        {
            "workspace_id": workspace.id,
            "subject_types": AgentSubjectType.type,
        },
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert [result["subject_id"] for result in response.json()["results"]] == [agent.id]
