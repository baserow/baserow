from unittest.mock import patch

from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.core.handler import CoreHandler
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.role.constants import NO_ROLE_LOW_PRIORITY_ROLE_UID
from baserow_enterprise.role.models import Role, WorkspaceScopedInvitation
from baserow_enterprise.teams.models import WorkspaceTeamInvitation
from baserow_enterprise.teams.operations import ReadTeamOperationType


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


def role(uid):
    return Role.objects.get(uid=uid)


def setup_workspace(data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace, name="CRM")
    customers = data_fixture.create_database_table(
        database=database, user=user, name="Customers"
    )
    orders = data_fixture.create_database_table(
        database=database, user=user, name="Orders"
    )
    return user, token, workspace, database, customers, orders


def invite_to(invitation, scope, role_uid="VIEWER"):
    return WorkspaceScopedInvitation.objects.create(
        invitation=invitation, scope=scope, role=role(role_uid)
    )


def list_invitations(api_client, token, workspace):
    response = api_client.get(
        reverse(
            "api:workspaces:invitations:list", kwargs={"workspace_id": workspace.id}
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    return {invitation["email"]: invitation for invitation in response.json()}


@pytest.mark.django_db
def test_list_workspace_invitations_includes_scopes_and_teams(
    api_client, data_fixture, enterprise_data_fixture
):
    user, token, workspace, database, customers, orders = setup_workspace(data_fixture)
    view = data_fixture.create_grid_view(
        user=user, table=orders, name="Open orders", ownership_type="restricted"
    )
    team = enterprise_data_fixture.create_team(workspace=workspace, name="Ops")

    workspace_only = data_fixture.create_workspace_invitation(
        workspace=workspace, email="workspace@test.nl", permissions="MEMBER"
    )
    scoped = data_fixture.create_workspace_invitation(
        workspace=workspace,
        email="scoped@test.nl",
        permissions=NO_ROLE_LOW_PRIORITY_ROLE_UID,
    )
    invite_to(scoped, customers, "EDITOR")
    invite_to(scoped, database, "VIEWER")
    invite_to(scoped, view, "COMMENTER")
    WorkspaceTeamInvitation.objects.create(invitation=scoped, team=team)

    invitations = list_invitations(api_client, token, workspace)

    assert invitations["workspace@test.nl"]["id"] == workspace_only.id
    assert invitations["workspace@test.nl"]["scopes"] == []
    assert invitations["workspace@test.nl"]["teams"] == []
    assert invitations["scoped@test.nl"]["scopes"] == [
        {
            "scope_type": "database_table",
            "scope_id": customers.id,
            "name": "Customers",
            "role": "EDITOR",
        },
        {
            "scope_type": "application",
            "scope_id": database.id,
            "name": "CRM",
            "role": "VIEWER",
        },
        {
            "scope_type": "database_view",
            "scope_id": view.id,
            "name": "Open orders",
            "role": "COMMENTER",
        },
    ]
    assert invitations["scoped@test.nl"]["teams"] == [{"id": team.id, "name": "Ops"}]


@pytest.mark.django_db
def test_list_workspace_invitations_leaves_out_trashed_scopes_and_teams(
    api_client, data_fixture, enterprise_data_fixture
):
    user, token, workspace, database, customers, orders = setup_workspace(data_fixture)
    other_database = data_fixture.create_database_application(workspace=workspace)
    table_in_trashed_database = data_fixture.create_database_table(
        database=other_database, user=user
    )
    team = enterprise_data_fixture.create_team(workspace=workspace, name="Ops")
    trashed_team = enterprise_data_fixture.create_team(workspace=workspace, name="Old")

    invitation = data_fixture.create_workspace_invitation(
        workspace=workspace, email="scoped@test.nl"
    )
    invite_to(invitation, customers)
    invite_to(invitation, orders)
    invite_to(invitation, table_in_trashed_database)
    WorkspaceTeamInvitation.objects.create(invitation=invitation, team=team)
    WorkspaceTeamInvitation.objects.create(invitation=invitation, team=trashed_team)

    TrashHandler.trash(user, workspace, database, orders)
    TrashHandler.trash(user, workspace, other_database, other_database)
    trashed_team.trashed = True
    trashed_team.save()

    invitations = list_invitations(api_client, token, workspace)

    assert [scope["scope_id"] for scope in invitations["scoped@test.nl"]["scopes"]] == [
        customers.id
    ]
    assert invitations["scoped@test.nl"]["teams"] == [{"id": team.id, "name": "Ops"}]


@pytest.mark.django_db
def test_list_workspace_invitations_only_shows_what_the_user_may_read(
    api_client, data_fixture, enterprise_data_fixture
):
    user, token, workspace, database, customers, orders = setup_workspace(data_fixture)
    team = enterprise_data_fixture.create_team(workspace=workspace, name="Ops")
    hidden_team = enterprise_data_fixture.create_team(
        workspace=workspace, name="Hidden"
    )

    invitation = data_fixture.create_workspace_invitation(
        workspace=workspace, email="scoped@test.nl"
    )
    invite_to(invitation, customers)
    invite_to(invitation, orders)
    WorkspaceTeamInvitation.objects.create(invitation=invitation, team=team)
    WorkspaceTeamInvitation.objects.create(invitation=invitation, team=hidden_team)

    check_multiple_permissions = CoreHandler.check_multiple_permissions
    denied = {
        ("database.table.read_role", orders.id),
        (ReadTeamOperationType.type, hidden_team.id),
    }

    def deny_some(self, checks, *args, **kwargs):
        result = check_multiple_permissions(self, checks, *args, **kwargs)
        for check in checks:
            if (check.operation_name, check.context.id) in denied:
                result[check] = False
        return result

    with patch.object(CoreHandler, "check_multiple_permissions", deny_some):
        invitations = list_invitations(api_client, token, workspace)

    assert [scope["name"] for scope in invitations["scoped@test.nl"]["scopes"]] == [
        "Customers"
    ]
    assert invitations["scoped@test.nl"]["teams"] == [{"id": team.id, "name": "Ops"}]


@pytest.mark.django_db
def test_list_workspace_invitations_query_count_does_not_grow_per_invitation(
    api_client, data_fixture, enterprise_data_fixture
):
    user, token, workspace, database, customers, orders = setup_workspace(data_fixture)
    team = enterprise_data_fixture.create_team(workspace=workspace)

    def add_invitation(index):
        invitation = data_fixture.create_workspace_invitation(
            workspace=workspace, email=f"person{index}@test.nl"
        )
        # A view of its own on every invitation, as the check whether a view is in
        # the trash goes through its table and database.
        view = data_fixture.create_grid_view(
            user=user, table=orders, ownership_type="restricted"
        )
        invite_to(invitation, customers)
        invite_to(invitation, orders)
        invite_to(invitation, database)
        invite_to(invitation, view)
        WorkspaceTeamInvitation.objects.create(invitation=invitation, team=team)

    def count_queries():
        # Creating objects resets caches the request warms, so both counts are
        # taken warm.
        list_invitations(api_client, token, workspace)
        list_invitations(api_client, token, workspace)
        with CaptureQueriesContext(connection) as queries:
            invitations = list_invitations(api_client, token, workspace)
        return invitations, len(queries.captured_queries)

    add_invitation(0)
    _, one_invitation_queries = count_queries()

    for index in range(1, 6):
        add_invitation(index)
    invitations, six_invitations_queries = count_queries()

    assert len(invitations) == 6
    assert all(len(invitation["scopes"]) == 4 for invitation in invitations.values())
    assert six_invitations_queries == one_invitation_queries


@pytest.mark.django_db
def test_updating_a_workspace_invitation_returns_its_scopes_and_teams(
    api_client, data_fixture, enterprise_data_fixture
):
    user, token, workspace, database, customers, orders = setup_workspace(data_fixture)
    team = enterprise_data_fixture.create_team(workspace=workspace, name="Ops")
    invitation = data_fixture.create_workspace_invitation(
        workspace=workspace,
        email="scoped@test.nl",
        permissions=NO_ROLE_LOW_PRIORITY_ROLE_UID,
    )
    invite_to(invitation, customers)
    WorkspaceTeamInvitation.objects.create(invitation=invitation, team=team)

    response = api_client.patch(
        reverse(
            "api:workspaces:invitations:item",
            kwargs={"workspace_invitation_id": invitation.id},
        ),
        {"permissions": "MEMBER"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["permissions"] == "MEMBER"
    assert [scope["name"] for scope in response_json["scopes"]] == ["Customers"]
    assert response_json["teams"] == [{"id": team.id, "name": "Ops"}]

    response = api_client.get(
        reverse(
            "api:workspaces:invitations:item",
            kwargs={"workspace_invitation_id": invitation.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert [scope["name"] for scope in response.json()["scopes"]] == ["Customers"]
