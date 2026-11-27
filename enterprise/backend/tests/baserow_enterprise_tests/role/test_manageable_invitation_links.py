from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.core.handler import CoreHandler
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.role.constants import NO_ROLE_LOW_PRIORITY_ROLE_UID
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_enterprise.teams.handler import TeamHandler


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


def role(uid):
    return Role.objects.get(uid=uid)


def add_member(data_fixture, workspace, permissions):
    member = data_fixture.create_user()
    data_fixture.create_user_workspace(
        workspace=workspace, user=member, permissions=permissions
    )
    return member


def setup_links(data_fixture):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    database = data_fixture.create_database_application(workspace=workspace, name="CRM")
    table_a = data_fixture.create_database_table(
        database=database, user=admin, name="Customers"
    )
    table_b = data_fixture.create_database_table(
        database=database, user=admin, name="Orders"
    )
    team = TeamHandler().create_team(
        admin, "Ops", workspace, default_role=role("EDITOR")
    )
    role_handler = RoleAssignmentHandler()
    links = {
        "workspace": CoreHandler().create_workspace_invitation_link(
            admin, workspace, "VIEWER", "Everyone"
        ),
        "database": role_handler.create_scoped_invitation_link(
            admin, workspace, database.application_ptr, role("BUILDER"), "Builders"
        ),
        "table_a": role_handler.create_scoped_invitation_link(
            admin, workspace, table_a, role("EDITOR"), "Customers"
        ),
        "table_b": role_handler.create_scoped_invitation_link(
            admin, workspace, table_b, role("VIEWER"), "Orders"
        ),
        "team": TeamHandler().create_team_invitation_link(admin, team, "Ops"),
    }
    return admin, workspace, database, table_a, table_b, team, links


def manageable_ids(user, workspace):
    return [
        link.id
        for link in CoreHandler().list_manageable_workspace_invitation_links(
            user, workspace
        )
    ]


@pytest.mark.django_db
def test_workspace_admin_manages_every_link_of_the_workspace(data_fixture):
    admin, workspace, *_, links = setup_links(data_fixture)
    other_workspace = data_fixture.create_workspace(user=admin)
    data_fixture.create_workspace_invitation_link(workspace=other_workspace)

    assert manageable_ids(admin, workspace) == [
        links["workspace"].id,
        links["database"].id,
        links["table_a"].id,
        links["table_b"].id,
        links["team"].id,
    ]


@pytest.mark.django_db
def test_object_admin_only_manages_the_links_of_their_object(data_fixture):
    _, workspace, database, table_a, _, _, links = setup_links(data_fixture)
    table_admin = add_member(data_fixture, workspace, NO_ROLE_LOW_PRIORITY_ROLE_UID)
    database_admin = add_member(data_fixture, workspace, NO_ROLE_LOW_PRIORITY_ROLE_UID)
    table_editor = add_member(data_fixture, workspace, NO_ROLE_LOW_PRIORITY_ROLE_UID)
    builder = add_member(data_fixture, workspace, "BUILDER")
    role_handler = RoleAssignmentHandler()
    role_handler.assign_role(table_admin, workspace, role("ADMIN"), table_a)
    role_handler.assign_role(
        database_admin, workspace, role("ADMIN"), database.application_ptr
    )
    role_handler.assign_role(table_editor, workspace, role("EDITOR"), table_a)

    assert manageable_ids(table_admin, workspace) == [links["table_a"].id]
    # The admin role on the database also applies to its tables.
    assert manageable_ids(database_admin, workspace) == [
        links["database"].id,
        links["table_a"].id,
        links["table_b"].id,
    ]
    assert manageable_ids(table_editor, workspace) == []
    assert manageable_ids(builder, workspace) == []


@pytest.mark.django_db
def test_links_to_trashed_objects_or_without_license_are_not_listed(
    data_fixture, enterprise_data_fixture
):
    admin, workspace, _, table_a, _, team, links = setup_links(data_fixture)

    TrashHandler.trash(admin, workspace, None, table_a)
    TrashHandler.trash(admin, workspace, None, team)
    assert manageable_ids(admin, workspace) == [
        links["workspace"].id,
        links["database"].id,
        links["table_b"].id,
    ]

    enterprise_data_fixture.delete_all_licenses()
    assert manageable_ids(admin, workspace) == [links["workspace"].id]


@pytest.mark.django_db
def test_list_manageable_invitation_links_with_their_objects(api_client, data_fixture):
    admin, workspace, database, table_a, _, team, links = setup_links(data_fixture)
    view = data_fixture.create_grid_view(
        table=table_a, name="Open deals", ownership_type="restricted"
    )
    links["view"] = RoleAssignmentHandler().create_scoped_invitation_link(
        admin, workspace, view, role("VIEWER")
    )
    token = data_fixture.generate_token(admin)

    response = api_client.get(
        reverse(
            "api:workspaces:invitation_links:manageable",
            kwargs={"workspace_id": workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    by_id = {link["id"]: link for link in response.json()}
    assert by_id[links["workspace"].id]["scope_type"] is None
    assert by_id[links["workspace"].id]["scope"] is None
    assert by_id[links["workspace"].id]["permissions"] == "VIEWER"
    assert by_id[links["database"].id]["scope_type"] == "application"
    assert by_id[links["database"].id]["scope"] == {
        "id": database.id,
        "name": "CRM",
        "type": "database",
    }
    assert by_id[links["table_a"].id]["scope_type"] == "database_table"
    assert by_id[links["table_a"].id]["scope"] == {
        "id": table_a.id,
        "name": "Customers",
    }
    assert by_id[links["table_a"].id]["permissions"] == "EDITOR"
    assert by_id[links["view"].id]["scope_type"] == "database_view"
    assert by_id[links["view"].id]["scope"] == {
        "id": view.id,
        "name": "Open deals",
        "table_name": "Customers",
    }
    assert by_id[links["team"].id]["scope_type"] == "team"
    assert by_id[links["team"].id]["scope"] == {
        "id": team.id,
        "name": "Ops",
        "default_role": "EDITOR",
    }


def count_listing_queries(admin, workspace):
    handler = CoreHandler()
    with CaptureQueriesContext(connection) as captured:
        links = handler.list_manageable_workspace_invitation_links(admin, workspace)
        handler.get_invitation_links_scope_data(links)
    return len(links), len(captured.captured_queries)


def add_link_of_every_kind(data_fixture, admin, workspace, name):
    role_handler = RoleAssignmentHandler()
    application = data_fixture.create_database_application(workspace=workspace)
    role_handler.create_scoped_invitation_link(
        admin, workspace, application.application_ptr, role("BUILDER")
    )
    table = data_fixture.create_database_table(database=application, user=admin)
    role_handler.create_scoped_invitation_link(admin, workspace, table, role("EDITOR"))
    view = data_fixture.create_grid_view(table=table, ownership_type="restricted")
    role_handler.create_scoped_invitation_link(admin, workspace, view, role("VIEWER"))
    team = TeamHandler().create_team(
        admin, name, workspace, default_role=role("VIEWER")
    )
    TeamHandler().create_team_invitation_link(admin, team)
    CoreHandler().create_workspace_invitation_link(admin, workspace, "VIEWER")


@pytest.mark.django_db
def test_listing_manageable_links_does_not_query_per_link(data_fixture):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    add_link_of_every_kind(data_fixture, admin, workspace, "First")
    # Warms up the caches that a first request fills, like the content types.
    count_listing_queries(admin, workspace)
    links_before, queries_before = count_listing_queries(admin, workspace)

    for index in range(3):
        add_link_of_every_kind(data_fixture, admin, workspace, f"Team {index}")

    links_after, queries_after = count_listing_queries(admin, workspace)
    assert links_after == links_before + 15
    assert queries_after == queries_before
