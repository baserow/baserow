from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.core.cache import local_cache
from baserow.core.models import Agent
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


def assign(subject, workspace, role_uid, scope):
    RoleAssignmentHandler().assign_role(
        subject, workspace, role=Role.objects.get(uid=role_uid), scope=scope
    )


def list_subject_role_assignments(api_client, token, workspace, params):
    return api_client.get(
        reverse(
            "api:enterprise:role:subject_role_assignments",
            kwargs={"workspace_id": workspace.id},
        ),
        params,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


@pytest.mark.django_db
def test_list_subject_role_assignments(api_client, data_fixture):
    admin, token = data_fixture.create_user_and_token()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin, name="Widelab", custom_permissions=[(member, "EDITOR")]
    )
    projects = data_fixture.create_database_application(
        workspace=workspace, name="Projects"
    )
    tasks = data_fixture.create_database_table(database=projects, name="Tasks")
    gallery = data_fixture.create_gallery_view(
        table=tasks, name="Gallery - Q3", ownership_type="restricted"
    )
    assign(member, workspace, "BUILDER", projects.application_ptr)
    assign(member, workspace, "BUILDER", tasks)
    assign(member, workspace, "EDITOR", gallery.view_ptr)

    response = list_subject_role_assignments(
        api_client,
        token,
        workspace,
        {"subject_type": "auth.User", "subject_id": member.id},
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 3,
        "next": None,
        "previous": None,
        "results": [
            {
                "scope_type": "application",
                "scope_id": projects.id,
                "name": "Projects",
                "type": "database",
                "parents": [],
                "role": "BUILDER",
                "locked_by": None,
            },
            {
                "scope_type": "database_table",
                "scope_id": tasks.id,
                "name": "Tasks",
                "type": None,
                "parents": [
                    {
                        "scope_type": "application",
                        "scope_id": projects.id,
                        "name": "Projects",
                    }
                ],
                "role": "BUILDER",
                "locked_by": None,
            },
            {
                "scope_type": "database_view",
                "scope_id": gallery.id,
                "name": "Gallery - Q3",
                "type": "gallery",
                "parents": [
                    {
                        "scope_type": "application",
                        "scope_id": projects.id,
                        "name": "Projects",
                    },
                    {
                        "scope_type": "database_table",
                        "scope_id": tasks.id,
                        "name": "Tasks",
                    },
                ],
                "role": "EDITOR",
                "locked_by": None,
            },
        ],
    }


@pytest.mark.django_db
def test_list_subject_role_assignments_pages_and_locks(api_client, data_fixture):
    admin, token = data_fixture.create_user_and_token()
    other_admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin, custom_permissions=[(other_admin, "ADMIN")]
    )
    database = data_fixture.create_database_application(workspace=workspace)
    tables = [
        data_fixture.create_database_table(database=database, name=f"Table {index}")
        for index in range(3)
    ]
    for table in tables:
        assign(other_admin, workspace, "NO_ACCESS", table)

    response = list_subject_role_assignments(
        api_client,
        token,
        workspace,
        {
            "subject_type": "auth.User",
            "subject_id": other_admin.id,
            "limit": 2,
            "offset": 2,
        },
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 3
    assert [row["name"] for row in response_json["results"]] == ["Table 2"]
    assert response_json["results"][0]["locked_by"] == {
        "scope_type": "workspace",
        "scope_id": workspace.id,
        "name": workspace.name,
    }


@pytest.mark.django_db
def test_list_subject_role_assignments_of_teams_and_agents(
    api_client, data_fixture, enterprise_data_fixture
):
    admin, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin)
    table = data_fixture.create_database_table(user=admin)
    table.database.workspace = workspace
    table.database.save()
    team = enterprise_data_fixture.create_team(workspace=workspace)
    agent = Agent.objects.create(workspace=workspace, name="Bot", role_uid="VIEWER")
    assign(team, workspace, "EDITOR", table)
    assign(agent, workspace, "VIEWER", table)

    for subject_type, subject_id, role in [
        ("baserow_enterprise.Team", team.id, "EDITOR"),
        ("core.Agent", agent.id, "VIEWER"),
    ]:
        response = list_subject_role_assignments(
            api_client,
            token,
            workspace,
            {"subject_type": subject_type, "subject_id": subject_id},
        )
        assert response.status_code == HTTP_200_OK
        assert [row["role"] for row in response.json()["results"]] == [role]


@pytest.mark.django_db
def test_list_subject_role_assignments_denied(api_client, data_fixture):
    admin = data_fixture.create_user()
    viewer, token = data_fixture.create_user_and_token()
    member = data_fixture.create_user()
    outsider = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin, custom_permissions=[(viewer, "VIEWER"), (member, "EDITOR")]
    )

    # Listing the workspace's users takes at least the editor role.
    response = list_subject_role_assignments(
        api_client,
        token,
        workspace,
        {"subject_type": "auth.User", "subject_id": member.id},
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    admin_token = data_fixture.generate_token(admin)
    response = list_subject_role_assignments(
        api_client,
        admin_token,
        workspace,
        {"subject_type": "auth.User", "subject_id": outsider.id},
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_SUBJECT_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_lists_of_members_teams_and_agents_count_their_roles(
    api_client, data_fixture, enterprise_data_fixture
):
    admin, token = data_fixture.create_user_and_token()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin, custom_permissions=[(member, "EDITOR")]
    )
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    team = enterprise_data_fixture.create_team(workspace=workspace)
    agent = Agent.objects.create(workspace=workspace, name="Bot", role_uid="VIEWER")
    assign(member, workspace, "VIEWER", database.application_ptr)
    assign(member, workspace, "EDITOR", table)
    assign(team, workspace, "EDITOR", table)
    assign(agent, workspace, "NO_ACCESS", table)
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    response = api_client.get(
        reverse("api:workspaces:users:list", kwargs={"workspace_id": workspace.id}),
        **auth,
    )
    assert response.status_code == HTTP_200_OK
    assert {
        item["user_id"]: item["role_assignment_count"] for item in response.json()
    } == {admin.id: 0, member.id: 2}

    response = api_client.get(
        reverse("api:enterprise:teams:list", kwargs={"workspace_id": workspace.id}),
        **auth,
    )
    assert response.status_code == HTTP_200_OK
    assert [item["role_assignment_count"] for item in response.json()] == [1]

    response = api_client.get(
        reverse("api:agents:workspace", kwargs={"workspace_id": workspace.id}),
        **auth,
    )
    assert response.status_code == HTTP_200_OK
    assert [item["role_assignment_count"] for item in response.json()["results"]] == [1]


@pytest.mark.django_db
def test_counting_roles_of_members_does_not_grow_queries(api_client, data_fixture):
    admin, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin)
    database = data_fixture.create_database_application(workspace=workspace)
    url = reverse("api:workspaces:users:list", kwargs={"workspace_id": workspace.id})

    def add_members(count):
        for _ in range(count):
            member = data_fixture.create_user(workspace=workspace)
            table = data_fixture.create_database_table(database=database)
            assign(member, workspace, "EDITOR", table)
            assign(member, workspace, "VIEWER", database.application_ptr)

    def count_queries():
        local_cache.clear()
        with CaptureQueriesContext(connection) as queries:
            response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_200_OK
        return len(queries.captured_queries)

    add_members(2)
    count_queries()
    queries_with_few_members = count_queries()
    add_members(8)

    assert count_queries() == queries_with_few_members


def test_agents_list_documents_its_role_assignment_count():
    from baserow.api.agents.serializers import AgentListSerializer, AgentSerializer

    # The count is only added to the agents of a list response.
    assert "role_assignment_count" in AgentListSerializer().fields
    assert "role_assignment_count" not in AgentSerializer().fields
