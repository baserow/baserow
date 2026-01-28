from django.apps import apps
from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED, HTTP_404_NOT_FOUND

from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import OWNERSHIP_TYPE_COLLABORATIVE
from baserow.contrib.database.views.operations import (
    CreateAndUsePersonalViewOperationType,
)
from baserow.core.apps import sync_operations_after_migrate
from baserow_enterprise.apps import sync_default_roles_after_migrate
from baserow_enterprise.role.default_roles import default_roles
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_premium.views.models import OWNERSHIP_TYPE_PERSONAL


@pytest.fixture(autouse=True)
def enable_enterprise_for_all_tests_here(enable_enterprise, synced_roles):
    pass


@pytest.mark.django_db(transaction=True)
@pytest.mark.view_ownership
def test_personal_views_created_by_editor_cant_be_shared_publicly(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user)
    view = data_fixture.create_grid_view(
        user, table=table, owned_by=user, ownership_type=OWNERSHIP_TYPE_PERSONAL
    )
    editor_role = RoleAssignmentHandler().get_role_by_uid("EDITOR")
    RoleAssignmentHandler().assign_role(
        user, table.database.workspace, role=editor_role, scope=table
    )
    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": view.id}),
        {
            "public": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    view.refresh_from_db()
    assert not view.public
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db(transaction=True)
@pytest.mark.view_ownership
def test_personal_views_created_by_builder_can_be_shared_publicly(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user)
    view = data_fixture.create_grid_view(
        user, table=table, owned_by=user, ownership_type=OWNERSHIP_TYPE_PERSONAL
    )
    builder = RoleAssignmentHandler().get_role_by_uid("BUILDER")
    RoleAssignmentHandler().assign_role(
        user, table.database.workspace, role=builder, scope=table
    )
    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": view.id}),
        {
            "public": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    view.refresh_from_db()
    assert view.public
    assert response.status_code == HTTP_200_OK
    assert response.json()["public"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.view_ownership
def test_personal_views_shared_by_builder_stops_working_if_builder_looses_table_access(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user)
    view = data_fixture.create_grid_view(
        user,
        table=table,
        owned_by=user,
        ownership_type=OWNERSHIP_TYPE_PERSONAL,
        public=True,
    )
    builder = RoleAssignmentHandler().get_role_by_uid("BUILDER")
    editor = RoleAssignmentHandler().get_role_by_uid("EDITOR")
    RoleAssignmentHandler().assign_role(
        user, table.database.workspace, role=builder, scope=table
    )
    url = reverse("api:database:views:grid:public_rows", kwargs={"slug": view.slug})
    response = api_client.get(f"{url}")
    assert response.status_code == HTTP_200_OK
    RoleAssignmentHandler().assign_role(
        user, table.database.workspace, role=editor, scope=table
    )
    response = api_client.get(f"{url}")
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db(transaction=True)
@pytest.mark.view_ownership
def test_viewer_can_make_personal_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user)
    viewer = RoleAssignmentHandler().get_role_by_uid("VIEWER")
    RoleAssignmentHandler().assign_role(
        user, table.database.workspace, role=viewer, scope=table
    )
    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {"name": "Test 1", "type": "grid", "ownership_type": "personal"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db(transaction=True)
@pytest.mark.view_ownership
def test_viewer_cant_make_public_personal_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user)
    viewer = RoleAssignmentHandler().get_role_by_uid("VIEWER")
    RoleAssignmentHandler().assign_role(
        user, table.database.workspace, role=viewer, scope=table
    )
    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "grid",
            "ownership_type": "personal",
            "public": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db(transaction=True)
@pytest.mark.view_ownership
def test_builder_can_make_public_personal_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user)
    builder = RoleAssignmentHandler().get_role_by_uid("BUILDER")
    RoleAssignmentHandler().assign_role(
        user, table.database.workspace, role=builder, scope=table
    )
    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "grid",
            "ownership_type": "personal",
            "public": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["public"]
    assert response.json()["ownership_type"] == "personal"


@pytest.mark.django_db(transaction=True)
@pytest.mark.view_ownership
def test_viewer_cant_make_collab_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user)
    viewer = RoleAssignmentHandler().get_role_by_uid("VIEWER")
    RoleAssignmentHandler().assign_role(
        user, table.database.workspace, role=viewer, scope=table
    )
    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {"name": "Test 1", "type": "grid"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db(transaction=True)
@pytest.mark.view_ownership
def test_viewer_can_create_filter_on_their_own_personal_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user)
    field = data_fixture.create_text_field(table=table)
    viewer = RoleAssignmentHandler().get_role_by_uid("VIEWER")
    RoleAssignmentHandler().assign_role(
        user, table.database.workspace, role=viewer, scope=table
    )
    view = data_fixture.create_grid_view(
        user, table=table, owned_by=user, ownership_type=OWNERSHIP_TYPE_PERSONAL
    )
    response = api_client.post(
        reverse("api:database:views:list_filters", kwargs={"view_id": view.id}),
        {"field": field.id, "type": "equal", "value": "test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db(transaction=True)
@pytest.mark.view_ownership
def test_viewer_cant_create_filter_on_someone_elses_personal_view(
    api_client, data_fixture
):
    workspace = data_fixture.create_workspace()
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        workspace=workspace,
    )
    user2 = data_fixture.create_user(workspace=workspace)
    table = data_fixture.create_database_table(user)
    field = data_fixture.create_text_field(table=table)
    viewer = RoleAssignmentHandler().get_role_by_uid("VIEWER")
    RoleAssignmentHandler().assign_role(
        user, table.database.workspace, role=viewer, scope=table
    )
    view = data_fixture.create_grid_view(
        user2, table=table, owned_by=user2, ownership_type=OWNERSHIP_TYPE_PERSONAL
    )
    response = api_client.post(
        reverse("api:database:views:list_filters", kwargs={"view_id": view.id}),
        {"field": field.id, "type": "equal", "value": "test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db(transaction=True)
@pytest.mark.view_ownership
def test_viewer_cant_submit_their_own_personal_form_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user)
    field = data_fixture.create_text_field(table=table)
    viewer = RoleAssignmentHandler().get_role_by_uid("VIEWER")
    RoleAssignmentHandler().assign_role(
        user, table.database.workspace, role=viewer, scope=table
    )
    view = data_fixture.create_form_view(
        user, table=table, owned_by=user, ownership_type=OWNERSHIP_TYPE_PERSONAL
    )
    data_fixture.create_form_view_field_option(
        view,
        field,
        name="Text field title",
        description="Text field description",
        required=True,
        enabled=True,
        order=1,
    )
    url = reverse(
        "api:database:views:form:submit",
        kwargs={"slug": view.slug},
    )
    response = api_client.post(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db(transaction=True)
@pytest.mark.view_ownership
@override_settings(DEBUG=True)
def test_list_views_doesnt_include_personal_views_the_user_used_to_have(data_fixture):
    role_that_looses_personal_views = "EDITOR"
    default_roles[role_that_looses_personal_views].remove(
        CreateAndUsePersonalViewOperationType
    )
    # Force resync as we've changed BASEROW_PERSONAL_VIEW_LOWEST_ROLE_ALLOWED
    # just for this one test
    sync_operations_after_migrate(None, apps=apps)
    sync_default_roles_after_migrate(None, apps=apps)
    RoleAssignmentHandler._init = False

    workspace = data_fixture.create_workspace(name="Workspace 1")
    user = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    handler = ViewHandler()
    builder = RoleAssignmentHandler().get_role_by_uid("BUILDER")
    editor = RoleAssignmentHandler().get_role_by_uid(role_that_looses_personal_views)
    RoleAssignmentHandler().assign_role(
        user, table.database.workspace, role=builder, scope=table
    )
    personal_view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type=OWNERSHIP_TYPE_PERSONAL,
    )
    collab_view = handler.create_view(
        user=user,
        table=table,
        type_name="grid",
        name="Test grid",
        ownership_type=OWNERSHIP_TYPE_COLLABORATIVE,
    )

    user_views = handler.list_views(user, table, "grid", False, False, False, False, 10)
    assert {v.id for v in user_views} == {
        personal_view.id,
        collab_view.id,
    }

    # Now they loose the ability to make and use personal views
    RoleAssignmentHandler().assign_role(
        user, table.database.workspace, role=editor, scope=table
    )
    user_views = handler.list_views(user, table, "grid", False, False, False, False, 10)
    assert {v.id for v in user_views} == {
        collab_view.id,
    }


VIEW_FILTER_RBAC_TESTS_PRAMS = [
    ("VIEWER", OWNERSHIP_TYPE_PERSONAL, HTTP_200_OK),
    ("EDITOR", OWNERSHIP_TYPE_COLLABORATIVE, HTTP_401_UNAUTHORIZED),
    ("BUILDER", OWNERSHIP_TYPE_COLLABORATIVE, HTTP_200_OK),
]


@pytest.mark.django_db(transaction=True)
@pytest.mark.view_ownership
@pytest.mark.parametrize(
    "role,ownership_type,expected_status_code", VIEW_FILTER_RBAC_TESTS_PRAMS
)
def test_viewer_can_create_filters_and_filter_groups_in_personal_views(
    api_client, data_fixture, role, ownership_type, expected_status_code
):
    workspace = data_fixture.create_workspace()
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        workspace=workspace,
    )
    table = data_fixture.create_database_table(user)
    field = data_fixture.create_text_field(table=table)
    viewer = RoleAssignmentHandler().get_role_by_uid(role)
    RoleAssignmentHandler().assign_role(
        user, table.database.workspace, role=viewer, scope=table
    )
    view = data_fixture.create_grid_view(
        user, table=table, owned_by=user, ownership_type=ownership_type
    )
    response = api_client.post(
        reverse("api:database:views:list_filter_groups", kwargs={"view_id": view.id}),
        {"filter_type": "OR"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == expected_status_code
    group_id = None
    if expected_status_code == HTTP_200_OK:
        assert response.json()["filter_type"] == "OR"
        group_id = response.json()["id"]

    response = api_client.post(
        reverse("api:database:views:list_filters", kwargs={"view_id": view.id}),
        {"field": field.id, "type": "equal", "value": "test", "group": group_id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == expected_status_code
    if expected_status_code == HTTP_200_OK:
        assert response.json()["id"] is not None
        assert response.json()["group"] == group_id


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "role,initial_ownership_type,final_ownership_type,expected_status_code",
    [
        ("ADMIN", OWNERSHIP_TYPE_COLLABORATIVE, OWNERSHIP_TYPE_PERSONAL, HTTP_200_OK),
        ("ADMIN", OWNERSHIP_TYPE_PERSONAL, OWNERSHIP_TYPE_COLLABORATIVE, HTTP_200_OK),
        ("BUILDER", OWNERSHIP_TYPE_COLLABORATIVE, OWNERSHIP_TYPE_PERSONAL, HTTP_200_OK),
        ("BUILDER", OWNERSHIP_TYPE_PERSONAL, OWNERSHIP_TYPE_COLLABORATIVE, HTTP_200_OK),
        (
            "EDITOR",
            OWNERSHIP_TYPE_COLLABORATIVE,
            OWNERSHIP_TYPE_PERSONAL,
            HTTP_401_UNAUTHORIZED,
        ),
        (
            "EDITOR",
            OWNERSHIP_TYPE_PERSONAL,
            OWNERSHIP_TYPE_COLLABORATIVE,
            HTTP_401_UNAUTHORIZED,
        ),
    ],
)
@pytest.mark.view_ownership
def test_builders_and_up_can_change_views_ownership_type(
    api_client,
    data_fixture,
    role,
    initial_ownership_type,
    final_ownership_type,
    expected_status_code,
):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user)
    view = data_fixture.create_grid_view(
        user, table=table, owned_by=user, ownership_type=initial_ownership_type
    )

    rbac_role = RoleAssignmentHandler().get_role_by_uid(role)
    RoleAssignmentHandler().assign_role(
        user, table.database.workspace, role=rbac_role, scope=table
    )

    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": view.id}),
        {"ownership_type": final_ownership_type},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == expected_status_code

    view.refresh_from_db()
    expected_ownership_type = (
        final_ownership_type
        if expected_status_code == HTTP_200_OK
        else initial_ownership_type
    )
    assert view.ownership_type == expected_ownership_type
