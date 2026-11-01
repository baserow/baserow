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


def get_effective_access(api_client, token, workspace, scope_type, scope_id):
    return api_client.get(
        reverse(
            "api:enterprise:role:effective_access",
            kwargs={"workspace_id": workspace.id},
        ),
        {"scope_type": scope_type, "scope_id": scope_id},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


@pytest.mark.django_db
def test_list_effective_access_of_a_table(
    api_client, data_fixture, enterprise_data_fixture
):
    admin, token = data_fixture.create_user_and_token()
    member = data_fixture.create_user()
    blocked = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin,
        custom_permissions=[
            (member, "NO_ROLE_LOW_PRIORITY"),
            (blocked, "EDITOR"),
        ],
    )
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    agent = Agent.objects.create(workspace=workspace, name="Bot", role_uid="VIEWER")
    team = enterprise_data_fixture.create_team(
        workspace=workspace, name="Sales", members=[member]
    )
    assign(team, workspace, "EDITOR", database.application_ptr)
    assign(blocked, workspace, "NO_ACCESS", database.application_ptr)

    response = get_effective_access(
        api_client, token, workspace, "database_table", table.id
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == [
        {
            "subject_type": "auth.User",
            "subject_id": admin.id,
            "role": "ADMIN",
            "source_scope_type": "workspace",
            "source_scope_id": workspace.id,
            "through_teams": False,
            "teams": [],
        },
        {
            "subject_type": "auth.User",
            "subject_id": member.id,
            "role": "EDITOR",
            "source_scope_type": "application",
            "source_scope_id": database.id,
            "through_teams": True,
            "teams": [{"id": team.id, "name": "Sales"}],
        },
        {
            "subject_type": "core.Agent",
            "subject_id": agent.id,
            "role": "VIEWER",
            "source_scope_type": "workspace",
            "source_scope_id": workspace.id,
            "through_teams": False,
            "teams": [],
        },
    ]


@pytest.mark.django_db
def test_list_effective_access_of_the_workspace(api_client, data_fixture):
    admin, token = data_fixture.create_user_and_token()
    viewer = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin, custom_permissions=[(viewer, "VIEWER")]
    )

    response = get_effective_access(
        api_client, token, workspace, "workspace", workspace.id
    )

    assert response.status_code == HTTP_200_OK
    assert [
        (item["subject_id"], item["role"], item["source_scope_type"])
        for item in response.json()
    ] == [(admin.id, "ADMIN", "workspace"), (viewer.id, "VIEWER", "workspace")]


@pytest.mark.django_db
def test_list_effective_access_hides_teams_the_user_cannot_list(
    api_client, data_fixture, enterprise_data_fixture
):
    admin = data_fixture.create_user()
    database_admin, token = data_fixture.create_user_and_token()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin,
        custom_permissions=[
            (database_admin, "VIEWER"),
            (member, "NO_ACCESS"),
        ],
    )
    database = data_fixture.create_database_application(workspace=workspace)
    team = enterprise_data_fixture.create_team(
        workspace=workspace, name="Sales", members=[member]
    )
    assign(database_admin, workspace, "ADMIN", database.application_ptr)
    assign(team, workspace, "EDITOR", database.application_ptr)

    response = get_effective_access(
        api_client, token, workspace, "application", database.id
    )

    assert response.status_code == HTTP_200_OK
    member_access = next(
        item for item in response.json() if item["subject_id"] == member.id
    )
    assert member_access["through_teams"] is True
    assert member_access["teams"] == []


@pytest.mark.django_db
def test_list_effective_access_requires_the_read_role_operation(
    api_client, data_fixture
):
    admin = data_fixture.create_user()
    editor, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(
        user=admin, custom_permissions=[(editor, "EDITOR")]
    )
    table = data_fixture.create_database_table(user=admin)
    table.database.workspace = workspace
    table.database.save()

    response = get_effective_access(
        api_client, token, workspace, "database_table", table.id
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_list_effective_access_of_a_scope_outside_the_workspace(
    api_client, data_fixture
):
    admin, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin)
    other_workspace = data_fixture.create_workspace(user=admin)
    other_database = data_fixture.create_database_application(workspace=other_workspace)

    response = get_effective_access(
        api_client, token, workspace, "application", other_database.id
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_SCOPE_DOES_NOT_EXIST"

    response = get_effective_access(
        api_client, token, workspace, "workspace", other_workspace.id
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_SCOPE_DOES_NOT_EXIST"

    response = get_effective_access(
        api_client, token, workspace, "application", other_database.id + 1000
    )
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_list_effective_access_query_count_does_not_grow_with_members(
    api_client, data_fixture, enterprise_data_fixture
):
    admin, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    def add_members(count):
        for _ in range(count):
            member = data_fixture.create_user(workspace=workspace)
            team = enterprise_data_fixture.create_team(
                workspace=workspace, members=[member]
            )
            assign(team, workspace, "EDITOR", database.application_ptr)
            assign(member, workspace, "VIEWER", table)
            Agent.objects.create(workspace=workspace, name="Bot", role_uid="VIEWER")

    def count_queries():
        local_cache.clear()
        with CaptureQueriesContext(connection) as queries:
            response = get_effective_access(
                api_client, token, workspace, "database_table", table.id
            )
        assert response.status_code == HTTP_200_OK
        return len(queries.captured_queries)

    add_members(2)
    # Warms up the caches that last beyond a request, like the content types.
    count_queries()
    queries_with_few_members = count_queries()
    add_members(10)

    assert count_queries() == queries_with_few_members
