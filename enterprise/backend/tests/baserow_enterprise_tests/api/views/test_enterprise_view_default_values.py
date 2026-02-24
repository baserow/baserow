from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED

from baserow.contrib.database.views.models import View
from baserow.core.models import WorkspaceUser
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType
from baserow_premium.views.models import OWNERSHIP_TYPE_PERSONAL


@pytest.fixture(autouse=True)
def enable_enterprise_for_all_tests_here(enable_enterprise, synced_roles):
    pass


@pytest.mark.django_db
def test_get_default_values_user_builder(api_client, enterprise_data_fixture):
    user, token = enterprise_data_fixture.create_user_and_token()
    user_builder, token_builder = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    WorkspaceUser.objects.create(
        workspace=workspace, user=user_builder, permissions="MEMBER", order=1
    )
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database, user=user)
    text_field = enterprise_data_fixture.create_text_field(table=table, name="Text")
    grid = enterprise_data_fixture.create_grid_view(table=table)

    builder_role = Role.objects.get(uid="BUILDER")
    RoleAssignmentHandler().assign_role(
        user_builder, workspace, role=builder_role, scope=workspace
    )

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_builder}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json == {}


@pytest.mark.django_db
def test_get_default_values_user_editor(api_client, enterprise_data_fixture):
    user, token = enterprise_data_fixture.create_user_and_token()
    user_editor, token_editor = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    WorkspaceUser.objects.create(
        workspace=workspace, user=user_editor, permissions="MEMBER", order=1
    )
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database, user=user)
    text_field = enterprise_data_fixture.create_text_field(table=table, name="Text")
    grid = enterprise_data_fixture.create_grid_view(table=table)

    editor_role = Role.objects.get(uid="EDITOR")
    RoleAssignmentHandler().assign_role(
        user_editor, workspace, role=editor_role, scope=workspace
    )

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_editor}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED, response.json()
    response_json = response.json()
    assert response_json["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_patch_default_values_builder(api_client, enterprise_data_fixture):
    user, token = enterprise_data_fixture.create_user_and_token()
    user_builder, token_builder = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    WorkspaceUser.objects.create(
        workspace=workspace, user=user_builder, permissions="MEMBER", order=1
    )
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, name="Text")
    grid = enterprise_data_fixture.create_grid_view(table=table)

    builder_role = Role.objects.get(uid="BUILDER")
    RoleAssignmentHandler().assign_role(
        user_builder, workspace, role=builder_role, scope=workspace
    )

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {text_field.id: {"enabled": True, "value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_builder}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json == {f"{text_field.id}": {"field_type": "text", "value": None}}


@pytest.mark.django_db
def test_patch_default_values_editor(api_client, enterprise_data_fixture):
    user, token = enterprise_data_fixture.create_user_and_token()
    user_editor, token_editor = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    WorkspaceUser.objects.create(
        workspace=workspace, user=user_editor, permissions="MEMBER", order=1
    )
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, name="Text")
    grid = enterprise_data_fixture.create_grid_view(table=table)

    editor_role = Role.objects.get(uid="EDITOR")
    RoleAssignmentHandler().assign_role(
        user_editor, workspace, role=editor_role, scope=workspace
    )

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {text_field.id: {"enabled": True, "value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_editor}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED, response.json()
    response_json = response.json()
    assert response_json["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_get_default_values_admin_personal_view_denied(
    api_client, enterprise_data_fixture
):
    user, _ = enterprise_data_fixture.create_user_and_token()
    user_admin, token_admin = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    WorkspaceUser.objects.create(
        user=user_admin, workspace=workspace, permissions="MEMBER", order=1
    )
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database, user=user)
    text_field = enterprise_data_fixture.create_text_field(table=table, name="Text")
    grid = enterprise_data_fixture.create_grid_view(
        table=table, user=user, owned_by=user, ownership_type=OWNERSHIP_TYPE_PERSONAL
    )

    admin_role = Role.objects.get(uid="ADMIN")
    RoleAssignmentHandler().assign_role(
        user_admin, workspace, role=admin_role, scope=workspace
    )

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_admin}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED, response.json()
    response_json = response.json()
    assert response_json["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_patch_default_values_admin_personal_view_denied(
    api_client, enterprise_data_fixture
):
    user, _ = enterprise_data_fixture.create_user_and_token()
    user_admin, token_admin = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    WorkspaceUser.objects.create(
        user=user_admin, workspace=workspace, permissions="MEMBER", order=1
    )
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database, user=user)
    text_field = enterprise_data_fixture.create_text_field(table=table, name="Text")
    grid = enterprise_data_fixture.create_grid_view(
        table=table, user=user, owned_by=user, ownership_type=OWNERSHIP_TYPE_PERSONAL
    )

    admin_role = Role.objects.get(uid="ADMIN")
    RoleAssignmentHandler().assign_role(
        user_admin, workspace, role=admin_role, scope=workspace
    )

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {text_field.id: {"enabled": True, "value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_admin}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED, response.json()
    response_json = response.json()
    assert response_json["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_get_default_values_editor_personal_view_allowed(
    api_client, enterprise_data_fixture
):
    user, _ = enterprise_data_fixture.create_user_and_token()
    user_editor, token_editor = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    WorkspaceUser.objects.create(
        user=user_editor, workspace=workspace, permissions="MEMBER", order=1
    )

    editor_role = Role.objects.get(uid="EDITOR")
    RoleAssignmentHandler().assign_role(
        user_editor, workspace, role=editor_role, scope=workspace
    )

    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database, user=user)
    text_field = enterprise_data_fixture.create_text_field(table=table, name="Text")
    grid = enterprise_data_fixture.create_grid_view(
        table=table,
        user=user_editor,
        owned_by=user_editor,
        ownership_type=OWNERSHIP_TYPE_PERSONAL,
    )

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_editor}",
    )
    assert response.status_code == HTTP_200_OK, response.json()


@pytest.mark.django_db
def test_patch_default_values_editor_personal_view_allowed(
    api_client, enterprise_data_fixture
):
    user, _ = enterprise_data_fixture.create_user_and_token()
    user_editor, token_editor = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    WorkspaceUser.objects.create(
        user=user_editor, workspace=workspace, permissions="MEMBER", order=1
    )

    editor_role = Role.objects.get(uid="EDITOR")
    RoleAssignmentHandler().assign_role(
        user_editor, workspace, role=editor_role, scope=workspace
    )

    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database, user=user)
    text_field = enterprise_data_fixture.create_text_field(table=table, name="Text")
    grid = enterprise_data_fixture.create_grid_view(
        table=table,
        user=user_editor,
        owned_by=user_editor,
        ownership_type=OWNERSHIP_TYPE_PERSONAL,
    )

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {text_field.id: {"value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_editor}",
    )
    assert response.status_code == HTTP_200_OK, response.json()


@pytest.mark.django_db
def test_get_default_values_user_builder_only_table_access(
    api_client, enterprise_data_fixture
):
    user, token = enterprise_data_fixture.create_user_and_token()
    user_builder, token_builder = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    WorkspaceUser.objects.create(
        workspace=workspace, user=user_builder, permissions="MEMBER", order=1
    )
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database, user=user)
    text_field = enterprise_data_fixture.create_text_field(table=table, name="Text")
    grid = enterprise_data_fixture.create_grid_view(table=table)

    noaccess_role = Role.objects.get(uid="NO_ACCESS")
    builder_role = Role.objects.get(uid="BUILDER")

    RoleAssignmentHandler().assign_role(
        user_builder, workspace, role=noaccess_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user_builder, workspace, role=builder_role, scope=table
    )

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_builder}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json == {}


@pytest.mark.django_db
def test_get_default_values_editor_restricted_view_denied(
    api_client, enterprise_data_fixture
):
    user, _ = enterprise_data_fixture.create_user_and_token()
    user_editor, token_editor = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    WorkspaceUser.objects.create(
        user=user_editor, workspace=workspace, permissions="MEMBER", order=1
    )

    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database, user=user)
    text_field = enterprise_data_fixture.create_text_field(table=table, name="Text")
    restricted_grid = enterprise_data_fixture.create_grid_view(
        table=table,
        user=user_editor,
        owned_by=user_editor,
        ownership_type=RestrictedViewOwnershipType.type,
    )

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user_editor, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user_editor,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=restricted_grid.id),
    )

    url = reverse(
        "api:database:views:default_values", kwargs={"view_id": restricted_grid.id}
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_editor}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED, response.json()
    response_json = response.json()
    assert response_json["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_patch_default_values_editor_restricted_view_denied(
    api_client, enterprise_data_fixture
):
    user, _ = enterprise_data_fixture.create_user_and_token()
    user_editor, token_editor = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    WorkspaceUser.objects.create(
        user=user_editor, workspace=workspace, permissions="MEMBER", order=1
    )

    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database, user=user)
    text_field = enterprise_data_fixture.create_text_field(table=table, name="Text")
    restricted_grid = enterprise_data_fixture.create_grid_view(
        table=table,
        user=user_editor,
        owned_by=user_editor,
        ownership_type=RestrictedViewOwnershipType.type,
    )

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user_editor, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user_editor,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=restricted_grid.id),
    )

    url = reverse(
        "api:database:views:default_values", kwargs={"view_id": restricted_grid.id}
    )
    response = api_client.patch(
        url,
        {text_field.id: {"value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_editor}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED, response.json()
    response_json = response.json()
    assert response_json["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_get_default_values_builder_restricted_view_allowed(
    api_client, enterprise_data_fixture
):
    user, _ = enterprise_data_fixture.create_user_and_token()
    user_builder, token_builder = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    WorkspaceUser.objects.create(
        user=user_builder, workspace=workspace, permissions="MEMBER", order=1
    )

    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database, user=user)
    text_field = enterprise_data_fixture.create_text_field(table=table, name="Text")
    restricted_grid = enterprise_data_fixture.create_grid_view(
        table=table,
        user=user_builder,
        owned_by=user_builder,
        ownership_type=RestrictedViewOwnershipType.type,
    )

    builder_role = Role.objects.get(uid="BUILDER")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user_builder, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user_builder,
        workspace,
        role=builder_role,
        scope=View.objects.get(id=restricted_grid.id),
    )

    url = reverse(
        "api:database:views:default_values", kwargs={"view_id": restricted_grid.id}
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_builder}",
    )
    assert response.status_code == HTTP_200_OK, response.json()


@pytest.mark.django_db
def test_patch_default_values_builder_restricted_view_allowed(
    api_client, enterprise_data_fixture
):
    user, _ = enterprise_data_fixture.create_user_and_token()
    user_builder, token_builder = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    WorkspaceUser.objects.create(
        user=user_builder, workspace=workspace, permissions="MEMBER", order=1
    )

    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database, user=user)
    text_field = enterprise_data_fixture.create_text_field(table=table, name="Text")
    restricted_grid = enterprise_data_fixture.create_grid_view(
        table=table,
        user=user_builder,
        owned_by=user_builder,
        ownership_type=RestrictedViewOwnershipType.type,
    )

    builder_role = Role.objects.get(uid="BUILDER")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user_builder, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user_builder,
        workspace,
        role=builder_role,
        scope=View.objects.get(id=restricted_grid.id),
    )

    url = reverse(
        "api:database:views:default_values", kwargs={"view_id": restricted_grid.id}
    )
    response = api_client.patch(
        url,
        {text_field.id: {"value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_builder}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
