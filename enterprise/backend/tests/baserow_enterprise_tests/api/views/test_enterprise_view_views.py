from django.test.utils import override_settings
from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_401_UNAUTHORIZED,
    HTTP_402_PAYMENT_REQUIRED,
)

from baserow.contrib.database.views.models import View
from baserow.core.subjects import UserSubjectType
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType


@pytest.mark.django_db
def test_create_restricted_grid_view_without_license(
    api_client, enterprise_data_fixture
):
    user, token = enterprise_data_fixture.create_user_and_token()
    table = enterprise_data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "grid",
            "ownership_type": "restricted",
            "filter_type": "OR",
            "filters_disabled": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_restricted_grid_view_with_license(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    table = enterprise_data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "grid",
            "ownership_type": "restricted",
            "filter_type": "OR",
            "filters_disabled": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["ownership_type"] == "restricted"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_create_view_if_user_has_only_permissions_to_view(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[])
    enterprise_data_fixture.create_user_workspace(
        workspace=workspace, user=user2, permissions="NO_ACCESS", order=0
    )
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(user=user, database=database)
    view = enterprise_data_fixture.create_grid_view(table=table)

    editor_role = Role.objects.get(uid="EDITOR")

    response = api_client.post(
        reverse("api:enterprise:role:batch", kwargs={"workspace_id": workspace.id}),
        {
            "items": [
                {
                    "scope_id": view.id,
                    "scope_type": "database_view",
                    "subject_id": user2.id,
                    "subject_type": UserSubjectType.type,
                    "role": editor_role.uid,
                },
            ]
        },
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "grid",
            "filter_type": "OR",
            "filters_disabled": True,
            "ownership_type": "collaborative",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "grid",
            "filter_type": "OR",
            "filters_disabled": True,
            "ownership_type": "personal",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "grid",
            "filter_type": "OR",
            "filters_disabled": True,
            "ownership_type": "restricted",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_row_with_only_view_permissions(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    normal_view = enterprise_data_fixture.create_grid_view(table=table)
    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )

    # Create a row to fetch
    model = table.get_model()
    row = model.objects.create(**{f"field_{text_field.id}": "Visible value"})

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    workspace = table.database.workspace
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=restricted_view.id),
    )
    # This normally never happens, but for testing purposes, we want to make sure that
    # if a user has access to a non-restricted view, they still cannot get a row
    # via that view when they don't have table permissions.
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=normal_view.id),
    )

    base_url = reverse(
        "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
    )

    # Expect permission denied when trying to get a row without view parameter
    response = api_client.get(
        base_url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    # Expect permission denied when trying to get a row via a non-restricted view
    response = api_client.get(
        base_url + f"?view={normal_view.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    # Should succeed when using view parameter with restricted view
    response = api_client.get(
        base_url + f"?view={restricted_view.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == row.id
    assert response_json[f"field_{text_field.id}"] == "Visible value"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_get_row_outside_of_restricted_view(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    enterprise_data_fixture.create_grid_view(table=table)
    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    enterprise_data_fixture.create_view_filter(
        view=restricted_view, field=text_field, type="equal", value="ABC"
    )

    # Create rows: one visible in the restricted view, one not
    model = table.get_model()
    row_visible = model.objects.create(**{f"field_{text_field.id}": "ABC"})
    row_hidden = model.objects.create(**{f"field_{text_field.id}": "DEF"})

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=restricted_view.id),
    )

    # Should succeed when getting a row that is visible in the restricted view
    url_visible = reverse(
        "api:database:rows:item",
        kwargs={"table_id": table.id, "row_id": row_visible.id},
    )
    response = api_client.get(
        url_visible + f"?view={restricted_view.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK

    # Should fail when trying to get a row that is not visible in the restricted view
    url_hidden = reverse(
        "api:database:rows:item",
        kwargs={"table_id": table.id, "row_id": row_hidden.id},
    )
    response = api_client.get(
        url_hidden + f"?view={restricted_view.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_row_with_only_view_permissions(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    normal_view = enterprise_data_fixture.create_grid_view(table=table)
    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    workspace = table.database.workspace
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=restricted_view.id),
    )
    # This normally never happens, but for testing purposes, we want to make sure that
    # if a user has access to a view, that they cannot create a row because it's not a
    # restricted view.
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=normal_view.id),
    )

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})

    # Expect permission denied when trying to create a row in the table because the
    # user does not have access to the table.
    response = api_client.post(
        url,
        {f"field_{text_field.id}": "Test 1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    # Expect permission denied when trying to create a row in the table because this
    # view ownership type does not allow a user to create a row.
    response = api_client.post(
        url + f"?view={normal_view.id}",
        {f"field_{text_field.id}": "Test 1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    # Should come through because the user has access to the view.
    response = api_client.post(
        url + f"?view={restricted_view.id}",
        {f"field_{text_field.id}": "Test 1"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_rows_with_only_view_permissions(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    normal_view = enterprise_data_fixture.create_grid_view(table=table)
    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    workspace = table.database.workspace
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=restricted_view.id),
    )

    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})

    # Expect permission denied when trying to batch create rows without view parameter
    response = api_client.post(
        url,
        {
            "items": [
                {f"field_{text_field.id}": "Test 1"},
                {f"field_{text_field.id}": "Test 2"},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    response = api_client.post(
        url + f"?view={normal_view.id}",
        {
            "items": [
                {f"field_{text_field.id}": "Test 1"},
                {f"field_{text_field.id}": "Test 2"},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    # Should succeed when using view parameter with restricted view
    response = api_client.post(
        url + f"?view={restricted_view.id}",
        {
            "items": [
                {f"field_{text_field.id}": "Test 1"},
                {f"field_{text_field.id}": "Test 2"},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK
    assert len(response.json()["items"]) == 2


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_row_with_only_view_permissions(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    normal_view = enterprise_data_fixture.create_grid_view(table=table)
    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )

    # Create a row to update
    model = table.get_model()
    row = model.objects.create(**{f"field_{text_field.id}": "Original Value"})

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=restricted_view.id),
    )

    # Expect permission denied when trying to update row without view parameter
    response = api_client.patch(
        reverse(
            "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
        ),
        {f"field_{text_field.id}": "Updated Value"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    response = api_client.patch(
        reverse(
            "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
        )
        + f"?view={normal_view.id}",
        {f"field_{text_field.id}": "Updated Value"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    # Should succeed when using view parameter with restricted view
    response = api_client.patch(
        reverse(
            "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
        )
        + f"?view={restricted_view.id}",
        {f"field_{text_field.id}": "Updated Value"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()[f"field_{text_field.id}"] == "Updated Value"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_update_row_outside_of_restricted_view(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    enterprise_data_fixture.create_grid_view(table=table)
    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    enterprise_data_fixture.create_view_filter(
        view=restricted_view, field=text_field, type="equal", value="ABC"
    )

    # Create a row to update
    model = table.get_model()
    # This row is visible in the view.
    row1 = model.objects.create(**{f"field_{text_field.id}": "ABC"})
    # This row is not visible in the view because it does not match the filters.
    row2 = model.objects.create(**{f"field_{text_field.id}": "DEF"})

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=restricted_view.id),
    )

    # Should succeed when using view parameter with restricted view
    response = api_client.patch(
        reverse(
            "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row1.id}
        )
        + f"?view={restricted_view.id}",
        {f"field_{text_field.id}": "Updated Value"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.patch(
        reverse(
            "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row2.id}
        )
        + f"?view={restricted_view.id}",
        {f"field_{text_field.id}": "Updated Value"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_rows_with_only_view_permissions(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    normal_view = enterprise_data_fixture.create_grid_view(table=table)

    # Create rows to update
    model = table.get_model()
    row1 = model.objects.create(**{f"field_{text_field.id}": "Original 1"})
    row2 = model.objects.create(**{f"field_{text_field.id}": "Original 2"})

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=restricted_view.id),
    )

    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})

    # Expect permission denied when trying to batch update rows without view parameter
    response = api_client.patch(
        url,
        {
            "items": [
                {"id": row1.id, f"field_{text_field.id}": "Updated 1"},
                {"id": row2.id, f"field_{text_field.id}": "Updated 2"},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    response = api_client.patch(
        url + f"?view={normal_view.id}",
        {
            "items": [
                {"id": row1.id, f"field_{text_field.id}": "Updated 1"},
                {"id": row2.id, f"field_{text_field.id}": "Updated 2"},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    # Should succeed when using view parameter with restricted view
    response = api_client.patch(
        url + f"?view={restricted_view.id}",
        {
            "items": [
                {"id": row1.id, f"field_{text_field.id}": "Updated 1"},
                {"id": row2.id, f"field_{text_field.id}": "Updated 2"},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK
    assert len(response.json()["items"]) == 2
    assert response.json()["items"][0][f"field_{text_field.id}"] == "Updated 1"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_update_rows_outside_of_restricted_view_filters(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    enterprise_data_fixture.create_view_filter(
        view=restricted_view, field=text_field, type="equal", value="ABC"
    )

    # Create rows to update
    model = table.get_model()
    # This row is visible in the view.
    row1 = model.objects.create(**{f"field_{text_field.id}": "ABC"})
    # This row is not visible in the view because it does not match the filters.
    row2 = model.objects.create(**{f"field_{text_field.id}": "DEF"})

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=restricted_view.id),
    )

    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})

    response = api_client.patch(
        url + f"?view={restricted_view.id}",
        {
            "items": [
                {"id": row1.id, f"field_{text_field.id}": "Updated 1"},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.patch(
        url + f"?view={restricted_view.id}",
        {
            "items": [
                {"id": row2.id, f"field_{text_field.id}": "Updated 2"},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_row_with_only_view_permissions(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    normal_view = enterprise_data_fixture.create_grid_view(table=table)
    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )

    # Create a row to delete
    model = table.get_model()
    row = model.objects.create(**{f"field_{text_field.id}": "Delete Me"})

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=restricted_view.id),
    )

    # Expect permission denied when trying to delete row without view parameter
    response = api_client.delete(
        reverse(
            "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
        ),
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    response = api_client.delete(
        reverse(
            "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
        )
        + f"?view={normal_view.id}",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    # Should succeed when using view parameter with restricted view
    response = api_client.delete(
        reverse(
            "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row.id}
        )
        + f"?view={restricted_view.id}",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    # Verify row was soft deleted (trashed)
    row.refresh_from_db()
    assert getattr(row, "trashed") is True


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_delete_row_outside_of_restricted_view_filters(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    enterprise_data_fixture.create_view_filter(
        view=restricted_view, field=text_field, type="equal", value="ABC"
    )

    # Create a row to delete
    model = table.get_model()
    # This row is visible in the view.
    row1 = model.objects.create(**{f"field_{text_field.id}": "ABC"})
    # This row is not visible in the view because it does not match the filters.
    row2 = model.objects.create(**{f"field_{text_field.id}": "DEF"})

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=restricted_view.id),
    )

    response = api_client.delete(
        reverse(
            "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row1.id}
        )
        + f"?view={restricted_view.id}",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    # Should succeed when using view parameter with restricted view
    response = api_client.delete(
        reverse(
            "api:database:rows:item", kwargs={"table_id": table.id, "row_id": row2.id}
        )
        + f"?view={restricted_view.id}",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_rows_with_only_view_permissions(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    normal_view = enterprise_data_fixture.create_grid_view(table=table)
    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )

    # Create rows to delete
    model = table.get_model()
    row1 = model.objects.create(**{f"field_{text_field.id}": "Delete 1"})
    row2 = model.objects.create(**{f"field_{text_field.id}": "Delete 2"})
    row3 = model.objects.create(**{f"field_{text_field.id}": "Keep 3"})

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=restricted_view.id),
    )

    url = reverse("api:database:rows:batch-delete", kwargs={"table_id": table.id})

    # Expect permission denied when trying to batch delete rows without view parameter
    response = api_client.post(
        url,
        {"items": [row1.id, row2.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    response = api_client.post(
        url + f"?view={normal_view.id}",
        {"items": [row1.id, row2.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    # Should succeed when using view parameter with restricted view
    response = api_client.post(
        url + f"?view={restricted_view.id}",
        {"items": [row1.id, row2.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    # Verify rows were soft deleted (trashed)
    row1.refresh_from_db()
    row2.refresh_from_db()
    row3.refresh_from_db()
    assert getattr(row1, "trashed") is True
    assert getattr(row2, "trashed") is True
    assert getattr(row3, "trashed") is False


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_delete_rows_outside_of_restricted_view_filters(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    enterprise_data_fixture.create_grid_view(table=table)
    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    enterprise_data_fixture.create_view_filter(
        view=restricted_view, field=text_field, type="equal", value="ABC"
    )

    # Create rows to delete
    model = table.get_model()
    # This row is visible in the view.
    row1 = model.objects.create(**{f"field_{text_field.id}": "ABC"})
    # This row is not visible in the view because it does not match the filters.
    row2 = model.objects.create(**{f"field_{text_field.id}": "DEF"})

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=restricted_view.id),
    )

    url = reverse("api:database:rows:batch-delete", kwargs={"table_id": table.id})

    response = api_client.post(
        url + f"?view={restricted_view.id}",
        {"items": [row1.id, row2.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    response = api_client.post(
        url + f"?view={restricted_view.id}",
        {"items": [row1.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_update_rows_in_table_using_unrelated_view(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    table2 = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table2, ownership_type=RestrictedViewOwnershipType.type
    )

    model = table.get_model()
    row1 = model.objects.create(**{f"field_{text_field.id}": "ABC"})

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=restricted_view.id),
    )

    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})

    # The user does have access to the view, but the view does not belong to the
    # table, so it should result in an unauthorized error.
    response = api_client.patch(
        url + f"?view={restricted_view.id}",
        {
            "items": [
                {"id": row1.id, f"field_{text_field.id}": "Updated 1"},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
