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

    # Custom role not working (it needs to be implemented)
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

    assert rsp.status_code == HTTP_400_BAD_REQUEST

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
    }
    assert FieldPermissions.objects.count() == 0
    _assert_field_permissions_exceptions(can_write_exc=[], allow_in_forms_exc=[])
