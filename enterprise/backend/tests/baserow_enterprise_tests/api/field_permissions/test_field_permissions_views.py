from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_404_NOT_FOUND,
)

from baserow.core.handler import CoreHandler
from baserow_enterprise.field_permissions.handler import FieldPermissionsHandler
from baserow_enterprise.field_permissions.models import FieldPermissions
from baserow_enterprise.field_permissions.permission_manager import (
    FieldPermissionManagerType,
)
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_get_field_permissions(api_client, enterprise_data_fixture):
    user, token = enterprise_data_fixture.create_user_and_token()
    ext_user, ext_token = enterprise_data_fixture.create_user_and_token()
    database = enterprise_data_fixture.create_database_application(user=user)
    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)

    # Field not found
    rsp = api_client.get(
        reverse(
            "api:enterprise:field_permissions:item",
            kwargs={"field_id": 9999},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == HTTP_404_NOT_FOUND

    # User not in workspace
    rsp = api_client.get(
        reverse(
            "api:enterprise:field_permissions:item",
            kwargs={"field_id": field.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {ext_token}",
    )
    assert rsp.status_code == HTTP_400_BAD_REQUEST

    # Missing license
    rsp = api_client.get(
        reverse(
            "api:enterprise:field_permissions:item",
            kwargs={"field_id": field.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == HTTP_402_PAYMENT_REQUIRED

    enterprise_data_fixture.enable_enterprise()

    # Editors and lower cannot get field permissions
    editor_role = Role.objects.get(uid="EDITOR")
    RoleAssignmentHandler().assign_role(
        subject=user, workspace=database.workspace, role=editor_role, scope=database
    )

    rsp = api_client.get(
        reverse(
            "api:enterprise:field_permissions:item",
            kwargs={"field_id": field.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert rsp.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_update_field_permissions(api_client, enterprise_data_fixture):
    user, token = enterprise_data_fixture.create_user_and_token()
    ext_user, ext_token = enterprise_data_fixture.create_user_and_token()
    database = enterprise_data_fixture.create_database_application(user=user)
    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)

    # Field not found
    rsp = api_client.patch(
        reverse(
            "api:enterprise:field_permissions:item",
            kwargs={"field_id": 9999},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        data={"role": "NOBODY"},
    )

    assert rsp.status_code == HTTP_404_NOT_FOUND

    # Missing license
    rsp = api_client.patch(
        reverse(
            "api:enterprise:field_permissions:item",
            kwargs={"field_id": field.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        data={"role": "NOBODY"},
    )

    assert rsp.status_code == HTTP_402_PAYMENT_REQUIRED

    enterprise_data_fixture.enable_enterprise()

    # User not in workspace
    rsp = api_client.patch(
        reverse(
            "api:enterprise:field_permissions:item",
            kwargs={"field_id": field.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {ext_token}",
        data={"role": "NOBODY"},
    )
    assert rsp.status_code == HTTP_400_BAD_REQUEST

    # Editors and lower cannot get field permissions
    editor_role = Role.objects.get(uid="EDITOR")
    RoleAssignmentHandler().assign_role(
        subject=user,
        workspace=database.workspace,
        role=editor_role,
        scope=database,
    )

    rsp = api_client.patch(
        reverse(
            "api:enterprise:field_permissions:item",
            kwargs={"field_id": field.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        data={"role": "NOBODY"},
    )

    assert rsp.status_code == HTTP_401_UNAUTHORIZED

    # CUSTOM is valid and starts with an empty subject list when none is provided.
    builder_role = Role.objects.get(uid="BUILDER")
    RoleAssignmentHandler().assign_role(
        subject=user, workspace=database.workspace, role=builder_role, scope=database
    )

    rsp = api_client.patch(
        reverse(
            "api:enterprise:field_permissions:item",
            kwargs={"field_id": field.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        data={"role": "CUSTOM"},
    )

    assert rsp.status_code == HTTP_200_OK
    assert rsp.json()["role"] == "CUSTOM"
    assert rsp.json()["subjects"] == []

    rsp = api_client.patch(
        reverse(
            "api:enterprise:field_permissions:item",
            kwargs={"field_id": field.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        data={"role": "SOME_OTHER_NON_EXISTING_ROLE"},
    )

    assert rsp.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_builders_can_get_field_permissions(api_client, enterprise_data_fixture):
    user, token = enterprise_data_fixture.create_user_and_token()
    ext_user, ext_token = enterprise_data_fixture.create_user_and_token()
    database = enterprise_data_fixture.create_database_application(user=user)
    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)
    enterprise_data_fixture.enable_enterprise()

    builder_role = Role.objects.get(uid="BUILDER")
    RoleAssignmentHandler().assign_role(
        subject=user,
        workspace=database.workspace,
        role=builder_role,
        scope=database,
    )

    # Default field permissions for every field
    rsp = api_client.get(
        reverse(
            "api:enterprise:field_permissions:item",
            kwargs={"field_id": field.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert rsp.status_code == HTTP_200_OK
    assert rsp.json() == {
        "field_id": field.id,
        "role": "EDITOR",
        "allow_in_forms": True,
        "subjects": [],
    }

    FieldPermissionsHandler.update_field_permissions(user, field, "NOBODY", False)

    rsp = api_client.get(
        reverse(
            "api:enterprise:field_permissions:item",
            kwargs={"field_id": field.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert rsp.status_code == HTTP_200_OK
    assert rsp.json() == {
        "field_id": field.id,
        "role": "NOBODY",
        "allow_in_forms": False,
        "subjects": [],
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_builders_can_update_field_permissions(api_client, enterprise_data_fixture):
    user, token = enterprise_data_fixture.create_user_and_token()
    ext_user, ext_token = enterprise_data_fixture.create_user_and_token()
    database = enterprise_data_fixture.create_database_application(user=user)
    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)
    enterprise_data_fixture.enable_enterprise()

    builder_role = Role.objects.get(uid="BUILDER")
    RoleAssignmentHandler().assign_role(
        subject=user,
        workspace=database.workspace,
        role=builder_role,
        scope=database,
    )

    # Ensure the final permission object contains the right field permissions
    def _assert_field_permissions_exceptions(
        can_write_exc=None, allow_in_forms_exc=None
    ):
        permissions = CoreHandler().get_permissions(user, workspace=database.workspace)
        for perm_manager in permissions:
            if perm_manager["name"] != FieldPermissionManagerType.type:
                continue

            can_write_perms = perm_manager["permissions"][
                "database.table.field.write_values"
            ]["exceptions"]
            if can_write_exc is not None:
                assert can_write_exc == can_write_perms

            allow_in_forms_perms = perm_manager["permissions"][
                "database.table.field.submit_anonymous_values"
            ]["exceptions"]
            if allow_in_forms_exc is not None:
                assert allow_in_forms_exc == allow_in_forms_perms

    # NOBODY can write values
    rsp = api_client.patch(
        reverse(
            "api:enterprise:field_permissions:item",
            kwargs={"field_id": field.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        data={"role": "NOBODY"},
    )
    assert rsp.status_code == HTTP_200_OK
    assert rsp.json() == {
        "field_id": field.id,
        "role": "NOBODY",
        "allow_in_forms": False,
        "can_write_values": False,
        "subjects": [],
    }
    _assert_field_permissions_exceptions(
        can_write_exc=[field.id], allow_in_forms_exc=[field.id]
    )

    # Only admins can write values
    rsp = api_client.patch(
        reverse(
            "api:enterprise:field_permissions:item",
            kwargs={"field_id": field.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        data={"role": "ADMIN", "allow_in_forms": True},
    )
    assert rsp.status_code == HTTP_200_OK
    assert rsp.json() == {
        "field_id": field.id,
        "role": "ADMIN",
        "allow_in_forms": True,
        "can_write_values": False,
        "subjects": [],
    }
    _assert_field_permissions_exceptions(
        can_write_exc=[field.id], allow_in_forms_exc=[]
    )

    # Builders and higher can write values
    rsp = api_client.patch(
        reverse(
            "api:enterprise:field_permissions:item",
            kwargs={"field_id": field.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        data={"role": "BUILDER", "allow_in_forms": True},
    )
    assert rsp.status_code == HTTP_200_OK
    assert rsp.json() == {
        "field_id": field.id,
        "role": "BUILDER",
        "allow_in_forms": True,
        "can_write_values": True,
        "subjects": [],
    }
    _assert_field_permissions_exceptions(can_write_exc=[], allow_in_forms_exc=[])

    assert FieldPermissions.objects.count() == 1
    # Back to default. It removes the field permissions entry
    rsp = api_client.patch(
        reverse(
            "api:enterprise:field_permissions:item",
            kwargs={"field_id": field.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        data={"role": "EDITOR"},
    )
    assert rsp.status_code == HTTP_200_OK
    assert rsp.json() == {
        "field_id": field.id,
        "role": "EDITOR",
        "allow_in_forms": True,
        "can_write_values": True,
        "subjects": [],
    }
    assert FieldPermissions.objects.count() == 0
    _assert_field_permissions_exceptions(can_write_exc=[], allow_in_forms_exc=[])


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_can_configure_specific_field_permission_users_and_teams(
    api_client, enterprise_data_fixture, synced_roles
):
    user, token = enterprise_data_fixture.create_user_and_token(first_name="Builder")
    selected_user = enterprise_data_fixture.create_user(first_name="Ada")
    database = enterprise_data_fixture.create_database_application(user=user)
    workspace = database.workspace
    enterprise_data_fixture.create_user_workspace(
        user=selected_user, workspace=workspace, permissions="EDITOR"
    )
    team = enterprise_data_fixture.create_team(
        name="Development", workspace=workspace, members=[selected_user]
    )
    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)
    enterprise_data_fixture.enable_enterprise()

    url = reverse(
        "api:enterprise:field_permissions:item", kwargs={"field_id": field.id}
    )
    subjects = [
        {"subject_id": user.id, "subject_type": "auth.User"},
        {
            "subject_id": team.id,
            "subject_type": "baserow_enterprise.Team",
        },
    ]
    rsp = api_client.patch(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        data={"role": "CUSTOM", "subjects": subjects},
    )

    assert rsp.status_code == HTTP_200_OK
    assert rsp.json()["role"] == "CUSTOM"
    assert rsp.json()["can_write_values"] is True
    assert {
        (subject["subject_type"], subject["subject_id"])
        for subject in rsp.json()["subjects"]
    } == {
        ("auth.User", user.id),
        ("baserow_enterprise.Team", team.id),
    }
    team_subject = next(
        subject
        for subject in rsp.json()["subjects"]
        if subject["subject_type"] == "baserow_enterprise.Team"
    )
    assert team_subject["subject"]["name"] == "Development"

    rsp = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert rsp.status_code == HTTP_200_OK
    assert len(rsp.json()["subjects"]) == 2

    # Updating another CUSTOM setting without sending subjects preserves the list.
    rsp = api_client.patch(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        data={"role": "CUSTOM", "allow_in_forms": True},
    )
    assert rsp.status_code == HTTP_200_OK
    assert rsp.json()["allow_in_forms"] is True
    assert len(rsp.json()["subjects"]) == 2

    # Removing the requester from the explicit list immediately removes their write
    # permission, even though they remain an Admin in the workspace.
    rsp = api_client.patch(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        data={"role": "CUSTOM", "subjects": [subjects[1]]},
    )
    assert rsp.status_code == HTTP_200_OK
    assert rsp.json()["can_write_values"] is False
    assert len(rsp.json()["subjects"]) == 1


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_can_search_paginated_field_permission_subject_options(
    api_client, enterprise_data_fixture, synced_roles
):
    user, token = enterprise_data_fixture.create_user_and_token(
        first_name="Builder", email="builder@else.test"
    )
    first_user = enterprise_data_fixture.create_user(
        first_name="Person A", email="first@else.test"
    )
    second_user = enterprise_data_fixture.create_user(
        first_name="Person B", email="second@else.test"
    )
    outsider = enterprise_data_fixture.create_user(first_name="Person Outside")
    database = enterprise_data_fixture.create_database_application(user=user)
    workspace = database.workspace
    for member in [first_user, second_user]:
        enterprise_data_fixture.create_user_workspace(
            user=member, workspace=workspace, permissions="EDITOR"
        )
    team = enterprise_data_fixture.create_team(
        name="Person team",
        workspace=workspace,
        members=[first_user, second_user],
    )
    enterprise_data_fixture.create_team(
        name="Person trashed team", workspace=workspace, trashed=True
    )
    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)
    enterprise_data_fixture.enable_enterprise()
    builder_role = Role.objects.get(uid="BUILDER")
    RoleAssignmentHandler().assign_role(
        subject=user,
        workspace=workspace,
        role=builder_role,
        scope=database,
    )
    url = reverse(
        "api:enterprise:field_permissions:subject_options",
        kwargs={"field_id": field.id},
    )

    first_page = api_client.get(
        url,
        {"search": "person", "page": 1, "size": 2},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    second_page = api_client.get(
        url,
        {"search": "person", "page": 2, "size": 2},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert first_page.status_code == HTTP_200_OK
    assert second_page.status_code == HTTP_200_OK
    assert first_page.json()["count"] == 3
    assert len(first_page.json()["results"]) == 2
    options = first_page.json()["results"] + second_page.json()["results"]
    assert {(option["subject_type"], option["subject_id"]) for option in options} == {
        ("auth.User", first_user.id),
        ("auth.User", second_user.id),
        ("baserow_enterprise.Team", team.id),
    }
    team_option = next(
        option
        for option in options
        if option["subject_type"] == "baserow_enterprise.Team"
    )
    assert team_option["subject_count"] == 2
    assert all(option["subject_id"] != outsider.id for option in options)

    response = api_client.get(
        url,
        {
            "search": "person",
            "exclude_user_ids": str(first_user.id),
            "exclude_team_ids": str(team.id),
        },
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["subject_id"] == second_user.id
    assert response.json()["results"][0]["subject_type"] == "auth.User"

    editor_role = Role.objects.get(uid="EDITOR")
    RoleAssignmentHandler().assign_role(
        subject=user,
        workspace=workspace,
        role=editor_role,
        scope=database,
    )
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_add_invalid_specific_field_permission_subjects(
    api_client, enterprise_data_fixture, synced_roles
):
    user, token = enterprise_data_fixture.create_user_and_token()
    outsider = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)
    enterprise_data_fixture.enable_enterprise()
    url = reverse(
        "api:enterprise:field_permissions:item", kwargs={"field_id": field.id}
    )

    rsp = api_client.patch(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        data={
            "role": "CUSTOM",
            "subjects": [{"subject_id": outsider.id, "subject_type": "auth.User"}],
        },
    )
    assert rsp.status_code == HTTP_404_NOT_FOUND
    assert not FieldPermissions.objects.filter(field=field).exists()
    assert FieldPermissionsHandler._get_field_permission_subjects(field) == []

    duplicate = {"subject_id": user.id, "subject_type": "auth.User"}
    rsp = api_client.patch(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        data={"role": "CUSTOM", "subjects": [duplicate, duplicate]},
    )
    assert rsp.status_code == HTTP_400_BAD_REQUEST

    rsp = api_client.patch(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
        data={"role": "NOBODY", "subjects": [duplicate]},
    )
    assert rsp.status_code == HTTP_400_BAD_REQUEST
