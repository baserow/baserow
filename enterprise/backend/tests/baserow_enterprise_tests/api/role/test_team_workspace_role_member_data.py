from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.core.cache import local_cache
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


def assign(subject, workspace, role_uid, scope):
    RoleAssignmentHandler().assign_role(
        subject, workspace, role=Role.objects.get(uid=role_uid), scope=scope
    )


def list_team_workspace_roles(api_client, token, workspace):
    response = api_client.get(
        reverse("api:workspaces:users:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    return {item["user_id"]: item["team_workspace_role"] for item in response.json()}


@pytest.mark.django_db
def test_members_with_no_role_show_the_workspace_role_of_their_teams(
    api_client, data_fixture, enterprise_data_fixture
):
    admin, token = data_fixture.create_user_and_token()
    through_ops = data_fixture.create_user()
    through_two_teams = data_fixture.create_user()
    through_equal_teams = data_fixture.create_user()
    without_team_role = data_fixture.create_user()
    builder = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin,
        custom_permissions=[
            (through_ops, "NO_ROLE_LOW_PRIORITY"),
            (through_two_teams, "NO_ROLE_LOW_PRIORITY"),
            (through_equal_teams, "NO_ROLE_LOW_PRIORITY"),
            (without_team_role, "NO_ROLE_LOW_PRIORITY"),
            (builder, "BUILDER"),
        ],
    )
    ops = enterprise_data_fixture.create_team(
        workspace=workspace,
        name="Ops",
        members=[through_ops, through_two_teams, through_equal_teams, builder],
    )
    support = enterprise_data_fixture.create_team(
        workspace=workspace, name="Support", members=[through_two_teams]
    )
    finance = enterprise_data_fixture.create_team(
        workspace=workspace, name="Finance", members=[through_equal_teams]
    )
    # A team role on something else than the workspace doesn't give a workspace role.
    projects = enterprise_data_fixture.create_team(
        workspace=workspace, name="Projects", members=[without_team_role]
    )
    database = data_fixture.create_database_application(workspace=workspace)
    assign(ops, workspace, "EDITOR", workspace)
    assign(support, workspace, "VIEWER", workspace)
    assign(finance, workspace, "EDITOR", workspace)
    assign(projects, workspace, "ADMIN", database.application_ptr)

    assert list_team_workspace_roles(api_client, token, workspace) == {
        admin.id: None,
        through_ops.id: {
            "role_uid": "EDITOR",
            "teams": [{"id": ops.id, "name": "Ops"}],
        },
        # The roles of the teams add up, so only the team giving the role that
        # wins is named.
        through_two_teams.id: {
            "role_uid": "EDITOR",
            "teams": [{"id": ops.id, "name": "Ops"}],
        },
        through_equal_teams.id: {
            "role_uid": "EDITOR",
            "teams": [
                {"id": finance.id, "name": "Finance"},
                {"id": ops.id, "name": "Ops"},
            ],
        },
        without_team_role.id: None,
        # The stored workspace role wins over the team's, so nothing is added.
        builder.id: None,
    }


@pytest.mark.django_db
def test_team_workspace_roles_need_to_read_the_workspace_roles(
    api_client, data_fixture, enterprise_data_fixture
):
    admin = data_fixture.create_user()
    editor, token = data_fixture.create_user_and_token()
    no_role = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=admin,
        custom_permissions=[(editor, "EDITOR"), (no_role, "NO_ROLE_LOW_PRIORITY")],
    )
    ops = enterprise_data_fixture.create_team(
        workspace=workspace, name="Ops", members=[no_role]
    )
    assign(ops, workspace, "EDITOR", workspace)

    # An editor may list the members, but not read their roles.
    assert list_team_workspace_roles(api_client, token, workspace) == {
        admin.id: None,
        editor.id: None,
        no_role.id: None,
    }


@pytest.mark.django_db
def test_team_workspace_roles_of_members_do_not_grow_queries(
    api_client, data_fixture, enterprise_data_fixture
):
    admin, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin)
    url = reverse("api:workspaces:users:list", kwargs={"workspace_id": workspace.id})

    def add_members(count):
        for _ in range(count):
            member = data_fixture.create_user()
            data_fixture.create_user_workspace(
                user=member, workspace=workspace, permissions="NO_ROLE_LOW_PRIORITY"
            )
            team = enterprise_data_fixture.create_team(
                workspace=workspace, members=[member]
            )
            assign(team, workspace, "EDITOR", workspace)

    def count_queries():
        local_cache.clear()
        with CaptureQueriesContext(connection) as queries:
            response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_200_OK
        assert all(
            item["team_workspace_role"] is not None
            for item in response.json()
            if item["user_id"] != admin.id
        )
        return len(queries.captured_queries)

    add_members(2)
    count_queries()
    queries_with_few_members = count_queries()
    add_members(8)

    assert count_queries() == queries_with_few_members
