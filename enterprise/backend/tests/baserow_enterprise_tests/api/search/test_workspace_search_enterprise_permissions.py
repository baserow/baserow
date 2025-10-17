from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK

from baserow_enterprise.field_permissions.handler import FieldPermissionsHandler
from baserow_enterprise.field_permissions.models import FieldPermissionsRoleEnum
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_workspace_search_denies_access_without_workspace_permission(
    api_client, enterprise_data_fixture, enable_enterprise, synced_roles
):
    no_access_user, no_access_token = enterprise_data_fixture.create_user_and_token()
    admin_user, _ = enterprise_data_fixture.create_user_and_token()

    workspace = enterprise_data_fixture.create_workspace(
        users=[admin_user, no_access_user]
    )

    role_no_access = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(no_access_user, workspace, role=role_no_access)

    response = api_client.get(
        reverse("api:search:workspace_search", kwargs={"workspace_id": workspace.id}),
        {"query": "Table"},
        HTTP_AUTHORIZATION=f"JWT {no_access_token}",
    )
    assert response.status_code == 401  # Expected: no permission to access workspace


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_workspace_search_filters_tables_by_permissions(
    api_client, enterprise_data_fixture, enable_enterprise, synced_roles
):
    admin_user, admin_token = enterprise_data_fixture.create_user_and_token()
    viewer_user, viewer_token = enterprise_data_fixture.create_user_and_token()

    workspace = enterprise_data_fixture.create_workspace(
        users=[admin_user, viewer_user]
    )

    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table1, _, _ = enterprise_data_fixture.build_table(
        user=admin_user,
        columns=[("restricted_field", "text")],
        rows=[["secret data"]],
        database=database,
    )
    table2, _, _ = enterprise_data_fixture.build_table(
        user=admin_user,
        columns=[("public_field", "text")],
        rows=[["public data"]],
        database=database,
    )

    table1.name = "Restricted Table"
    table1.save()
    table2.name = "Public Table"
    table2.save()

    from baserow.contrib.database.search.handler import SearchHandler

    SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)
    SearchHandler.initialize_missing_search_data(table1)
    SearchHandler.initialize_missing_search_data(table2)

    role_admin = Role.objects.get(uid="ADMIN")
    role_viewer = Role.objects.get(uid="VIEWER")
    role_no_access = Role.objects.get(uid="NO_ACCESS")

    RoleAssignmentHandler().assign_role(admin_user, workspace, role=role_admin)

    RoleAssignmentHandler().assign_role(
        viewer_user, workspace, role=role_no_access, scope=database
    )
    RoleAssignmentHandler().assign_role(
        viewer_user, workspace, role=role_viewer, scope=table2
    )
    RoleAssignmentHandler().assign_role(
        viewer_user, workspace, role=role_no_access, scope=table1
    )

    response = api_client.get(
        reverse("api:search:workspace_search", kwargs={"workspace_id": workspace.id}),
        {"query": "Table"},
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    results = response.json()["results"]
    table_results = [r for r in results if r["type"] == "database_table"]
    assert len(table_results) == 2

    response = api_client.get(
        reverse("api:search:workspace_search", kwargs={"workspace_id": workspace.id}),
        {"query": "Table"},
        HTTP_AUTHORIZATION=f"JWT {viewer_token}",
    )
    assert response.status_code == HTTP_200_OK
    results = response.json()["results"]
    table_results = [r for r in results if r["type"] == "database_table"]
    assert len(table_results) == 1
    assert table_results[0]["title"] == "Public Table"


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_workspace_search_respects_field_permissions(
    api_client, enterprise_data_fixture, enable_enterprise, synced_roles
):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(users=[user])

    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table, fields, _ = enterprise_data_fixture.build_table(
        user=user,
        columns=[("public_field", "text"), ("restricted_field", "text")],
        rows=[["public data", "restricted data"]],
        database=database,
    )
    public_field, restricted_field = fields

    from baserow.contrib.database.search.handler import SearchHandler

    SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)
    SearchHandler.initialize_missing_search_data(table)

    FieldPermissionsHandler().update_field_permissions(
        user=user,
        field=restricted_field,
        role=FieldPermissionsRoleEnum.NOBODY.value,
        allow_in_forms=False,
    )

    response = api_client.get(
        reverse("api:search:workspace_search", kwargs={"workspace_id": workspace.id}),
        {"query": "data"},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    results = response.json()["results"]
    row_results = [r for r in results if r["type"] == "database_row"]

    for result in row_results:
        field_name = result["metadata"].get("field_name")
        assert field_name == "public_field"


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_workspace_search_team_permission_inheritance(
    api_client, enterprise_data_fixture, enable_enterprise, synced_roles
):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(users=[user])

    team = enterprise_data_fixture.create_team(
        workspace=workspace, name="Engineering Team"
    )
    enterprise_data_fixture.create_subject(team=team, subject=user)

    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table1 = enterprise_data_fixture.create_database_table(
        database=database, name="Team Table"
    )
    table2 = enterprise_data_fixture.create_database_table(
        database=database, name="Other Table"
    )

    from baserow.contrib.database.search.handler import SearchHandler

    SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)
    SearchHandler.initialize_missing_search_data(table1)
    SearchHandler.initialize_missing_search_data(table2)

    role_viewer = Role.objects.get(uid="VIEWER")
    role_no_access = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(team, workspace, role=role_viewer, scope=table1)
    RoleAssignmentHandler().assign_role(
        user, workspace, role=role_no_access, scope=table2
    )

    response = api_client.get(
        reverse("api:search:workspace_search", kwargs={"workspace_id": workspace.id}),
        {"query": "Table"},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    results = response.json()["results"]
    table_results = [r for r in results if r["type"] == "database_table"]
    assert len(table_results) == 1
    assert table_results[0]["title"] == "Team Table"


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_workspace_search_scope_inheritance(
    api_client, enterprise_data_fixture, enable_enterprise, synced_roles
):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(users=[user])

    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table, _, _ = enterprise_data_fixture.build_table(
        user=user,
        columns=[("test_field", "text")],
        rows=[["test data"]],
        database=database,
    )

    table.name = "Test Table"
    table.save()

    from baserow.contrib.database.search.handler import SearchHandler

    SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)
    SearchHandler.initialize_missing_search_data(table)

    role_viewer = Role.objects.get(uid="VIEWER")
    RoleAssignmentHandler().assign_role(
        user, workspace, role=role_viewer, scope=database
    )

    response = api_client.get(
        reverse("api:search:workspace_search", kwargs={"workspace_id": workspace.id}),
        {"query": "Test"},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    results = response.json()["results"]
    table_results = [r for r in results if r["type"] == "database_table"]
    assert len(table_results) == 1


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_workspace_search_no_role_low_priority_behavior(
    api_client, enterprise_data_fixture, enable_enterprise, synced_roles
):
    admin_user = enterprise_data_fixture.create_user()
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(users=[admin_user, user])

    team = enterprise_data_fixture.create_team(workspace=workspace)
    enterprise_data_fixture.create_subject(team=team, subject=user)

    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table, _, _ = enterprise_data_fixture.build_table(
        user=admin_user,
        columns=[("test_field", "text")],
        rows=[["test data"]],
        database=database,
    )

    table.name = "Team Table"
    table.save()

    from baserow.contrib.database.search.handler import SearchHandler

    SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)
    SearchHandler.initialize_missing_search_data(table)

    role_admin = Role.objects.get(uid="ADMIN")
    role_no_role_low_priority = Role.objects.get(uid="NO_ROLE_LOW_PRIORITY")
    role_viewer = Role.objects.get(uid="VIEWER")

    RoleAssignmentHandler().assign_role(admin_user, workspace, role=role_admin)
    RoleAssignmentHandler().assign_role(user, workspace, role=role_no_role_low_priority)
    RoleAssignmentHandler().assign_role(team, workspace, role=role_viewer, scope=table)

    response = api_client.get(
        reverse("api:search:workspace_search", kwargs={"workspace_id": workspace.id}),
        {"query": "Team"},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    results = response.json()["results"]
    table_results = [r for r in results if r["type"] == "database_table"]
    assert len(table_results) == 1


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_workspace_search_actor_role_precedence_over_team(
    api_client, enterprise_data_fixture, enable_enterprise, synced_roles
):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(users=[user])

    team = enterprise_data_fixture.create_team(workspace=workspace)
    enterprise_data_fixture.create_subject(team=team, subject=user)

    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table1 = enterprise_data_fixture.create_database_table(
        database=database, name="Table 1"
    )
    table2 = enterprise_data_fixture.create_database_table(
        database=database, name="Table 2"
    )

    from baserow.contrib.database.search.handler import SearchHandler

    SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)
    SearchHandler.initialize_missing_search_data(table1)
    SearchHandler.initialize_missing_search_data(table2)

    role_viewer = Role.objects.get(uid="VIEWER")
    role_no_access = Role.objects.get(uid="NO_ACCESS")

    RoleAssignmentHandler().assign_role(team, workspace, role=role_viewer, scope=table1)
    RoleAssignmentHandler().assign_role(
        user, workspace, role=role_no_access, scope=table1
    )
    RoleAssignmentHandler().assign_role(user, workspace, role=role_viewer, scope=table2)

    response = api_client.get(
        reverse("api:search:workspace_search", kwargs={"workspace_id": workspace.id}),
        {"query": "Table"},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    results = response.json()["results"]
    table_results = [r for r in results if r["type"] == "database_table"]
    assert len(table_results) == 1
    assert table_results[0]["title"] == "Table 2"


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_workspace_search_respects_table_access_permissions(
    api_client, enterprise_data_fixture, enable_enterprise, synced_roles
):
    user, token = enterprise_data_fixture.create_user_and_token()
    admin_user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(users=[user, admin_user])

    role_admin = Role.objects.get(uid="ADMIN")
    RoleAssignmentHandler().assign_role(admin_user, workspace, role=role_admin)

    database = enterprise_data_fixture.create_database_application(workspace=workspace)

    role_no_access = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user, workspace, role=role_no_access, scope=database
    )
    table, _, _ = enterprise_data_fixture.build_table(
        user=admin_user,
        columns=[("test_field", "text")],
        rows=[["test data"]],
        database=database,
    )

    table.name = "Restricted Table"
    table.save()

    from baserow.contrib.database.search.handler import SearchHandler

    SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)
    SearchHandler.initialize_missing_search_data(table)

    response = api_client.get(
        reverse("api:search:workspace_search", kwargs={"workspace_id": workspace.id}),
        {"query": "test"},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    results = response.json()["results"]
    table_results = [r for r in results if r["type"] == "database_table"]
    row_results = [r for r in results if r["type"] == "database_row"]
    assert len(table_results) == 0
    assert len(row_results) == 0


@pytest.mark.workspace_search
@pytest.mark.django_db(transaction=True)
def test_workspace_search_team_role_union_behavior(
    api_client, enterprise_data_fixture, enable_enterprise, synced_roles
):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(users=[user])

    team1 = enterprise_data_fixture.create_team(workspace=workspace, name="Team 1")
    team2 = enterprise_data_fixture.create_team(workspace=workspace, name="Team 2")
    enterprise_data_fixture.create_subject(team=team1, subject=user)
    enterprise_data_fixture.create_subject(team=team2, subject=user)

    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table1, _, _ = enterprise_data_fixture.build_table(
        user=user,
        columns=[("field1", "text")],
        rows=[["data1"]],
        database=database,
    )
    table2, _, _ = enterprise_data_fixture.build_table(
        user=user,
        columns=[("field2", "text")],
        rows=[["data2"]],
        database=database,
    )

    table1.name = "Table 1"
    table1.save()
    table2.name = "Table 2"
    table2.save()

    from baserow.contrib.database.search.handler import SearchHandler

    SearchHandler.create_workspace_search_table_if_not_exists(workspace.id)
    SearchHandler.initialize_missing_search_data(table1)
    SearchHandler.initialize_missing_search_data(table2)

    role_viewer = Role.objects.get(uid="VIEWER")
    RoleAssignmentHandler().assign_role(
        team1, workspace, role=role_viewer, scope=table1
    )
    RoleAssignmentHandler().assign_role(
        team2, workspace, role=role_viewer, scope=table2
    )

    response = api_client.get(
        reverse("api:search:workspace_search", kwargs={"workspace_id": workspace.id}),
        {"query": "Table"},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    results = response.json()["results"]
    table_results = [r for r in results if r["type"] == "database_table"]
    assert len(table_results) == 2
    table_names = [r["title"] for r in table_results]
    assert "Table 1" in table_names
    assert "Table 2" in table_names
