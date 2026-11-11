from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED

from baserow.core.agents.subjects import AgentSubjectType
from baserow.core.models import Agent
from baserow.core.subjects import UserSubjectType
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.teams.subjects import TeamSubjectType


@pytest.mark.django_db
def test_subject_options_cannot_list_teams_from_another_workspace(
    api_client, data_fixture, enterprise_data_fixture, enable_enterprise, synced_roles
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace()
    enterprise_data_fixture.create_team(workspace=workspace)

    response = api_client.get(
        reverse("api:subjects:list"),
        {
            "workspace_id": workspace.id,
            "subject_types": TeamSubjectType.type,
        },
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_subject_options_check_each_requested_type_permission(
    api_client, data_fixture, enable_enterprise, synced_roles
):
    admin = data_fixture.create_user()
    editor, editor_token = data_fixture.create_user_and_token()
    builder, builder_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin, members=[editor, builder])
    roles = RoleAssignmentHandler()
    roles.assign_role(editor, workspace, roles.get_role_by_uid("EDITOR"))
    roles.assign_role(builder, workspace, roles.get_role_by_uid("BUILDER"))
    agent = Agent.objects.create(workspace=workspace, name="Private agent")
    url = reverse("api:subjects:list")

    editor_users_response = api_client.get(
        url,
        {
            "workspace_id": workspace.id,
            "subject_types": UserSubjectType.type,
        },
        HTTP_AUTHORIZATION=f"JWT {editor_token}",
    )
    editor_agents_response = api_client.get(
        url,
        {
            "workspace_id": workspace.id,
            "subject_types": AgentSubjectType.type,
        },
        HTTP_AUTHORIZATION=f"JWT {editor_token}",
    )
    editor_all_response = api_client.get(
        url,
        {"workspace_id": workspace.id},
        HTTP_AUTHORIZATION=f"JWT {editor_token}",
    )
    builder_all_response = api_client.get(
        url,
        {"workspace_id": workspace.id},
        HTTP_AUTHORIZATION=f"JWT {builder_token}",
    )

    assert editor_users_response.status_code == HTTP_200_OK
    assert all(
        result["subject_type"] == UserSubjectType.type
        for result in editor_users_response.json()["results"]
    )
    assert editor_agents_response.status_code == HTTP_401_UNAUTHORIZED
    assert editor_all_response.status_code == HTTP_401_UNAUTHORIZED
    assert builder_all_response.status_code == HTTP_200_OK
    assert any(
        result["subject_type"] == AgentSubjectType.type
        and result["subject_id"] == agent.id
        for result in builder_all_response.json()["results"]
    )
