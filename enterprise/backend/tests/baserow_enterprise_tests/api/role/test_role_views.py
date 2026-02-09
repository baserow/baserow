from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from baserow.core.subjects import UserSubjectType
from baserow.test_utils.helpers import AnyInt
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role, RoleAssignment


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


@pytest.fixture(autouse=True)
def user_source_and_token(data_fixture):
    """A fixture to help test UserSourceSerializer."""

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    page = data_fixture.create_builder_page(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    user_source = data_fixture.create_user_source_with_first_type(
        application=application,
    )
    return (user_source, token)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_role_assignment(api_client, data_fixture, enterprise_data_fixture):
    user, token = data_fixture.create_user_and_token()
    user2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(
        user=user,
        custom_permissions=[(user2, "VIEWER")],
    )
    database = data_fixture.create_database_application(workspace=workspace)

    table = data_fixture.create_database_table(database=database, user=user)

    editor_role = Role.objects.get(uid="EDITOR")
    builder_role = Role.objects.get(uid="BUILDER")

    assert len(RoleAssignment.objects.all()) == 0

    url = reverse("api:enterprise:role:list", kwargs={"workspace_id": workspace.id})

    # Can add a first roleAssignment
    response = api_client.post(
        url,
        {
            "scope_id": table.id,
            "scope_type": "database_table",
            "subject_id": user2.id,
            "subject_type": UserSubjectType.type,
            "role": builder_role.uid,
        },
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    response_json = response.json()

    assert response.status_code == HTTP_200_OK

    role_assignment_user_2 = RoleAssignmentHandler().get_current_role_assignment(
        user2, workspace, scope=table
    )

    assert role_assignment_user_2.scope == table
    assert role_assignment_user_2.subject == user2
    assert role_assignment_user_2.role == builder_role
    assert role_assignment_user_2.workspace == workspace

    assert response_json == {
        "id": role_assignment_user_2.id,
        "role": builder_role.uid,
        "scope_id": table.id,
        "scope_type": "database_table",
        "subject_id": user2.id,
        "subject_type": UserSubjectType.type,
        "subject": {
            "email": user2.email,
            "first_name": user2.first_name,
            "id": user2.id,
            "username": user2.username,
        },
    }

    # Can we create another roleAssignment
    response = api_client.post(
        url,
        {
            "scope_id": workspace.id,
            "scope_type": "workspace",
            "subject_id": user2.id,
            "subject_type": UserSubjectType.type,
            "role": editor_role.uid,
        },
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    role_assignment_user_2 = RoleAssignmentHandler().get_current_role_assignment(
        user2, workspace
    )

    assert role_assignment_user_2.role == editor_role
    assert role_assignment_user_2.scope == workspace

    # Check that we don't create new RoleAssignment for the same scope/subject/workspace
    response = api_client.post(
        url,
        {
            "scope_id": table.id,
            "scope_type": "database_table",
            "subject_id": user2.id,
            "subject_type": UserSubjectType.type,
            "role": editor_role.uid,
        },
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    role_assignment_user_2 = RoleAssignmentHandler().get_current_role_assignment(
        user2, workspace, scope=table
    )

    assert role_assignment_user_2.role == editor_role
    assert role_assignment_user_2.scope == table

    # Can we remove a role
    response = api_client.post(
        url,
        {
            "scope_id": table.id,
            "scope_type": "database_table",
            "subject_id": user2.id,
            "subject_type": UserSubjectType.type,
            "role": None,
        },
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    role_assignment_user_2 = RoleAssignmentHandler().get_current_role_assignment(
        user2, workspace, scope=table
    )

    assert role_assignment_user_2 is None


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_role_assignment_invalid_requests(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_2 = data_fixture.create_user()
    user_3 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[user_2])
    workspace_2 = data_fixture.create_workspace()
    role = Role.objects.get(uid="ADMIN")
    builder_role = Role.objects.get(uid="BUILDER")

    url = reverse("api:enterprise:role:list", kwargs={"workspace_id": workspace.id})

    response = api_client.post(
        url,
        {
            "scope_id": 9999,
            "scope_type": "workspace",
            "subject_id": user_2.id,
            "subject_type": UserSubjectType.type,
            "role": role.uid,
        },
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_SCOPE_DOES_NOT_EXIST"

    response = api_client.post(
        url,
        {
            "scope_id": workspace.id,
            "scope_type": "nonsense",
            "subject_id": user_2.id,
            "subject_type": UserSubjectType.type,
            "role": role.uid,
        },
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_OBJECT_SCOPE_TYPE_DOES_NOT_EXIST"

    response = api_client.post(
        url,
        {
            "scope_id": workspace.id,
            "scope_type": "workspace",
            "subject_id": 99999,
            "subject_type": UserSubjectType.type,
            "role": role.uid,
        },
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_SUBJECT_DOES_NOT_EXIST"

    response = api_client.post(
        url,
        {
            "scope_id": workspace.id,
            "scope_type": "workspace",
            "subject_id": user_2.id,
            "subject_type": "nonsense",
            "role": role.uid,
        },
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_SUBJECT_TYPE_DOES_NOT_EXIST"

    response = api_client.post(
        url,
        {
            "scope_id": workspace.id,
            "scope_type": "workspace",
            "subject_id": user_2.id,
            "subject_type": UserSubjectType.type,
            "role": 999999,
        },
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROLE_DOES_NOT_EXIST"

    response = api_client.post(
        reverse("api:enterprise:role:list", kwargs={"workspace_id": workspace_2.id}),
        {
            "scope_id": workspace_2.id,
            "scope_type": "workspace",
            "subject_id": user_3.id,
            "subject_type": UserSubjectType.type,
            "role": role.uid,
        },
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_SUBJECT_DOES_NOT_EXIST"

    response = api_client.post(
        reverse("api:enterprise:role:list", kwargs={"workspace_id": 999999}),
        {
            "scope_id": workspace.id,
            "scope_type": "workspace",
            "subject_id": user_2.id,
            "subject_type": UserSubjectType.type,
            "role": role.uid,
        },
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    response = api_client.post(
        url,
        {
            "scope_id": workspace.id,
            "scope_type": "workspace",
            "subject_id": user.id,
            "subject_type": UserSubjectType.type,
            "role": builder_role.uid,
        },
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_LAST_ADMIN_OF_GROUP"


@pytest.mark.django_db
def test_assign_last_admin_the_admin_role_works(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    admin_role = Role.objects.get(uid="ADMIN")

    url = reverse("api:enterprise:role:list", kwargs={"workspace_id": workspace.id})

    response = api_client.post(
        url,
        {
            "scope_id": workspace.id,
            "scope_type": "workspace",
            "subject_id": user.id,
            "subject_type": UserSubjectType.type,
            "role": admin_role.uid,
        },
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_role_assignments_workspace_level(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    user_2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[user_2])

    url = reverse("api:enterprise:role:list", kwargs={"workspace_id": workspace.id})

    response = api_client.get(
        url,
        {
            "scope_id": workspace.id,
            "scope_type": "workspace",
        },
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 2
    assert response_json == [
        {
            "id": None,
            "role": "ADMIN",
            "scope_id": workspace.id,
            "scope_type": "workspace",
            "subject_id": user.id,
            "subject_type": "auth.User",
            "subject": {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "email": user.email,
            },
        },
        {
            "id": None,
            "role": "BUILDER",
            "scope_id": workspace.id,
            "scope_type": "workspace",
            "subject_id": user_2.id,
            "subject_type": "auth.User",
            "subject": {
                "id": user_2.id,
                "username": user_2.username,
                "first_name": user_2.first_name,
                "email": user_2.email,
            },
        },
    ]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_role_assignments_application_level(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    user_2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[user_2])
    database = data_fixture.create_database_application(workspace=workspace)

    admin_role = Role.objects.get(uid="ADMIN")

    role_assignment = RoleAssignmentHandler().assign_role(
        user_2, workspace, role=admin_role, scope=database.application_ptr
    )

    url = reverse("api:enterprise:role:list", kwargs={"workspace_id": workspace.id})

    # TODO test with crap scope_type
    response = api_client.get(
        url,
        {
            "scope_id": database.id,
            "scope_type": "application",
        },
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 1
    assert response_json == [
        {
            "id": role_assignment.id,
            "role": admin_role.uid,
            "scope_id": database.id,
            "scope_type": "application",
            "subject_id": user_2.id,
            "subject_type": "auth.User",
            "subject": {
                "id": user_2.id,
                "username": user_2.username,
                "first_name": user_2.first_name,
                "email": user_2.email,
            },
        },
    ]


@pytest.mark.django_db
def test_get_role_assignments_table_level(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    user_2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[user_2])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    admin_role = Role.objects.get(uid="ADMIN")

    role_assignment = RoleAssignmentHandler().assign_role(
        user_2, workspace, role=admin_role, scope=table
    )

    url = reverse("api:enterprise:role:list", kwargs={"workspace_id": workspace.id})

    response = api_client.get(
        url,
        {
            "scope_id": table.id,
            "scope_type": "database_table",
        },
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 1
    assert response_json == [
        {
            "id": role_assignment.id,
            "role": admin_role.uid,
            "scope_id": table.id,
            "scope_type": "database_table",
            "subject_id": user_2.id,
            "subject_type": "auth.User",
            "subject": {
                "id": user_2.id,
                "username": user_2.username,
                "first_name": user_2.first_name,
                "email": user_2.email,
            },
        },
    ]


@pytest.mark.django_db
def test_batch_assign_role(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    user2 = data_fixture.create_user()
    user3 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[user2, user3])
    database = data_fixture.create_database_application(workspace=workspace)

    table = data_fixture.create_database_table(user=user, database=database)

    builder_role = Role.objects.get(uid="BUILDER")
    viewer_role = Role.objects.get(uid="VIEWER")

    assert len(RoleAssignment.objects.all()) == 0

    url = reverse("api:enterprise:role:batch", kwargs={"workspace_id": workspace.id})

    RoleAssignmentHandler().assign_role(
        user3, workspace, viewer_role, scope=database.application_ptr
    )
    RoleAssignmentHandler().assign_role(user3, workspace, viewer_role, scope=table)

    # Can add a first roleAssignment
    response = api_client.post(
        url,
        {
            "items": [
                {
                    "scope_id": table.id,
                    "scope_type": "database_table",
                    "subject_id": user2.id,
                    "subject_type": UserSubjectType.type,
                    "role": builder_role.uid,
                },
                {
                    "scope_id": table.id,
                    "scope_type": "database_table",
                    "subject_id": user3.id,
                    "subject_type": UserSubjectType.type,
                    "role": None,
                },
                {
                    "scope_id": database.application_ptr.id,
                    "scope_type": "application",
                    "subject_id": user3.id,
                    "subject_type": UserSubjectType.type,
                    "role": None,
                },
            ]
        },
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    role_assignment_user_2 = RoleAssignmentHandler().get_current_role_assignment(
        user2, workspace, scope=table
    )

    assert role_assignment_user_2.scope == table
    assert role_assignment_user_2.subject == user2
    assert role_assignment_user_2.role == builder_role
    assert role_assignment_user_2.workspace == workspace

    assert response_json == [
        {
            "id": role_assignment_user_2.id,
            "role": builder_role.uid,
            "scope_id": table.id,
            "scope_type": "database_table",
            "subject_id": user2.id,
            "subject_type": UserSubjectType.type,
            "subject": {
                "email": user2.email,
                "first_name": user2.first_name,
                "id": user2.id,
                "username": user2.username,
            },
        },
        None,
        None,
    ]


@pytest.mark.django_db
def test_batch_assign_role_to_database_view(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    user2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[user2])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    view = data_fixture.create_grid_view(table=table)

    editor_role = Role.objects.get(uid="EDITOR")

    assert len(RoleAssignment.objects.all()) == 0

    url = reverse("api:enterprise:role:batch", kwargs={"workspace_id": workspace.id})

    response = api_client.post(
        url,
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
    response_json = response.json()
    assert response_json == [
        {
            "id": AnyInt(),
            "role": editor_role.uid,
            "scope_id": view.id,
            "scope_type": "database_view",
            "subject_id": user2.id,
            "subject_type": UserSubjectType.type,
            "subject": {
                "email": user2.email,
                "first_name": user2.first_name,
                "id": user2.id,
                "username": user2.username,
            },
        },
    ]


@pytest.mark.django_db
def test_batch_assign_role_duplicates(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    user2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[user2])
    database = data_fixture.create_database_application(workspace=workspace)

    table = data_fixture.create_database_table(user=user, database=database)

    builder_role = Role.objects.get(uid="BUILDER")

    url = reverse("api:enterprise:role:batch", kwargs={"workspace_id": workspace.id})

    role_assignment = {
        "scope_id": table.id,
        "scope_type": "database_table",
        "subject_id": user2.id,
        "subject_type": UserSubjectType.type,
        "role": builder_role.uid,
    }

    # Can add a first roleAssignment
    response = api_client.post(
        url,
        {"items": [role_assignment, role_assignment]},
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_DUPLICATE_ROLE_ASSIGNMENTS"
    assert (
        response.json()["detail"]
        == "The list of role assignments includes duplicates at indexes: [0]"
    )


@pytest.mark.django_db
def test_batch_assign_role_is_undoable(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_2 = data_fixture.create_user()
    user_3 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[user_2, user_3])
    role = Role.objects.get(uid="ADMIN")
    session_id = "TEST"

    url = reverse("api:enterprise:role:batch", kwargs={"workspace_id": workspace.id})

    initial_role_user_2 = (
        RoleAssignmentHandler()
        .get_current_role_assignment(user_2, workspace=workspace)
        .role
    )
    initial_role_user_3 = (
        RoleAssignmentHandler()
        .get_current_role_assignment(user_3, workspace=workspace)
        .role
    )

    role_assignments = [
        {
            "scope_id": workspace.id,
            "scope_type": "workspace",
            "subject_id": user_2.id,
            "subject_type": UserSubjectType.type,
            "role": role.uid,
        },
        {
            "scope_id": workspace.id,
            "scope_type": "workspace",
            "subject_id": user_3.id,
            "subject_type": UserSubjectType.type,
            "role": role.uid,
        },
    ]

    api_client.post(
        url,
        {"items": role_assignments},
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
        HTTP_CLIENTSESSIONID=session_id,
    )

    assert (
        RoleAssignmentHandler()
        .get_current_role_assignment(user_2, workspace=workspace)
        .role
        == role
    )
    assert (
        RoleAssignmentHandler()
        .get_current_role_assignment(user_3, workspace=workspace)
        .role
        == role
    )

    api_client.patch(
        reverse("api:user:undo"),
        {"scopes": {"root": True, "workspace": workspace.id}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_CLIENTSESSIONID=session_id,
    )

    assert (
        RoleAssignmentHandler()
        .get_current_role_assignment(user_2, workspace=workspace)
        .role
        == initial_role_user_2
    )

    assert (
        RoleAssignmentHandler()
        .get_current_role_assignment(user_3, workspace=workspace)
        .role
        == initial_role_user_3
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "roles,",
    [
        ["foo_role"],
        ["bar_role", "foo_role"],
        # Intentionally non-alphabetically sorted
        ["zoo_role", "bar_role", "foo_role"],
    ],
)
def test_list_roles_endpoint_returns_expected_data(
    api_client, data_fixture, user_source_and_token, roles
):
    """
    Ensure that if the User Source has roles, they are returned as a
    list of alphabetized strings.
    """

    user_source, token = user_source_and_token

    # Create a roles field and add some rows
    users_table = data_fixture.create_database_table(name="test_users")
    role_field = data_fixture.create_text_field(
        table=users_table, order=0, name="role", text_default=""
    )
    user_source.table = users_table
    user_source.role_field = role_field
    user_source.save()

    # Add some roles
    model = users_table.get_model()
    for role in roles:
        model.objects.create(**{f"field_{role_field.id}": role})

    url = reverse(
        "api:user_sources:list_roles",
        kwargs={"application_id": user_source.application.id},
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == [
        {
            "id": user_source.id,
            "roles": sorted(roles),
        }
    ]
