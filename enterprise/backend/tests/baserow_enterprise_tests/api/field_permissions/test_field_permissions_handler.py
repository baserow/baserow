from unittest.mock import patch

from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from pytest_unordered import unordered
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.exceptions import PermissionDenied
from baserow_enterprise.field_permissions.handler import FieldPermissionsHandler
from baserow_enterprise.field_permissions.models import FieldPermissionsRoleEnum
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_only_builder_and_up_can_get_field_permissions(
    enterprise_data_fixture, synced_roles
):
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)
    enterprise_data_fixture.enable_enterprise()

    editor_role = Role.objects.get(uid="EDITOR")
    RoleAssignmentHandler().assign_role(
        subject=user, workspace=database.workspace, role=editor_role, scope=database
    )

    with pytest.raises(PermissionDenied):
        FieldPermissionsHandler.get_field_permissions(user, field)

    builder_role = Role.objects.get(uid="BUILDER")
    RoleAssignmentHandler().assign_role(
        subject=user, workspace=database.workspace, role=builder_role, scope=database
    )

    field_permissions = FieldPermissionsHandler.get_field_permissions(user, field)
    assert field_permissions.field == field
    assert field_permissions.role == "EDITOR"
    assert field_permissions.allow_in_forms is True


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_only_builder_and_up_can_update_field_permissions(
    enterprise_data_fixture, synced_roles
):
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)
    enterprise_data_fixture.enable_enterprise()

    editor_role = Role.objects.get(uid="EDITOR")
    RoleAssignmentHandler().assign_role(
        subject=user, workspace=database.workspace, role=editor_role, scope=database
    )

    with pytest.raises(PermissionDenied):
        FieldPermissionsHandler.update_field_permissions(user, field, "EDITOR", True)

    builder_role = Role.objects.get(uid="BUILDER")
    RoleAssignmentHandler().assign_role(
        subject=user, workspace=database.workspace, role=builder_role, scope=database
    )

    field_permissions = FieldPermissionsHandler.update_field_permissions(
        user, field, "EDITOR", True
    )
    assert field_permissions.field == field
    assert field_permissions.role == "EDITOR"
    assert field_permissions.allow_in_forms is True
    assert field_permissions.can_write_values is True

    field_permissions = FieldPermissionsHandler.update_field_permissions(
        user, field, "NOBODY", False
    )
    assert field_permissions.field == field
    assert field_permissions.role == "NOBODY"
    assert field_permissions.allow_in_forms is False
    assert field_permissions.can_write_values is False


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_update_field_permissions_send_permissions_updated_signal(
    enterprise_data_fixture, synced_roles
):
    user = enterprise_data_fixture.create_user()
    test_user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(users=[user, test_user])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    field = enterprise_data_fixture.create_text_field(table=table)
    enterprise_data_fixture.enable_enterprise()

    builder_role = Role.objects.get(uid="BUILDER")
    RoleAssignmentHandler().assign_role(
        subject=user, workspace=database.workspace, role=builder_role, scope=database
    )

    with patch(
        "baserow_enterprise.signals.field_permissions_updated.send"
    ) as mocked_signal:
        FieldPermissionsHandler.update_field_permissions(user, field, "ADMIN", True)

        assert mocked_signal.call_count == 1
        assert mocked_signal.call_args[1]["user"] == user
        assert mocked_signal.call_args[1]["workspace"] == database.workspace
        assert mocked_signal.call_args[1]["field"] == field
        assert mocked_signal.call_args[1]["role"] == "ADMIN"
        assert mocked_signal.call_args[1]["allow_in_forms"] is True

    with patch("baserow.ws.tasks.broadcast_to_users.delay") as mocked_task:
        FieldPermissionsHandler.update_field_permissions(user, field, "NOBODY", True)
        assert mocked_task.call_count == 1
        assert mocked_task.call_args[0][0] == unordered([user.id, test_user.id])
        assert mocked_task.call_args[0][1] == {
            "type": "field_permissions_updated",
            "workspace_id": database.workspace.id,
            "field_id": field.id,
            "role": "NOBODY",
            "allow_in_forms": True,
        }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_create_or_update_rows_without_proper_permisisons(
    enterprise_data_fixture, synced_roles
):
    user = enterprise_data_fixture.create_user()
    test_user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(users=[user, test_user])
    database = enterprise_data_fixture.create_database_application(
        user=user, workspace=workspace
    )
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    number_field = enterprise_data_fixture.create_number_field(table=table)
    enterprise_data_fixture.enable_enterprise()
    model = table.get_model()

    (row,) = RowHandler().force_create_rows(user, table, [{}], model=model).created_rows

    def _assign_role(role):
        RoleAssignmentHandler().assign_role(
            subject=test_user,
            workspace=database.workspace,
            role=role,
            scope=database,
        )

    def _create_row_with_field_value(field, value):
        RowHandler().create_rows(
            user=test_user,
            table=table,
            rows_values=[{field.db_column: value}],
            model=model,
        )

    def _update_row_with_field_value(field, value):
        RowHandler().update_rows(
            user=test_user,
            table=table,
            rows_values=[{"id": row.id, field.db_column: value}],
            model=model,
        )

    def _import_rows_with_field_value(field, value):
        return RowHandler().import_rows(
            user=test_user,
            table=table,
            data=[[value]],
            configuration=None,
            validate=False,
        )

    _assign_role(Role.objects.get(uid="EDITOR"))

    with pytest.raises(ValueError):
        FieldPermissionsHandler.update_field_permissions(
            test_user, text_field, "NON_EXISTING_ROLE"
        )

    # Default: everyone with at least EDITOR role can edit the field
    FieldPermissionsHandler.update_field_permissions(user, text_field, "EDITOR")

    _update_row_with_field_value(text_field, "editor")
    _create_row_with_field_value(text_field, "editor")

    rows, _ = _import_rows_with_field_value(text_field, "editor")
    assert len(rows) == 1
    assert getattr(rows[0], text_field.db_column) == "editor"

    # BUILDER and up can edit the field
    FieldPermissionsHandler.update_field_permissions(
        user, text_field, FieldPermissionsRoleEnum.BUILDER
    )

    # cannot edit/create rows with the text_field
    with pytest.raises(PermissionDenied):
        _update_row_with_field_value(text_field, "builder")

    with pytest.raises(PermissionDenied):
        _create_row_with_field_value(text_field, "builder")

    # Import won't fail, it will just ignore unwritable fields
    rows, _ = _import_rows_with_field_value(text_field, "builder")
    assert len(rows) == 1
    assert getattr(rows[0], text_field.db_column) is None

    # test_user can still edit the number_field
    _update_row_with_field_value(number_field, 1)
    _create_row_with_field_value(number_field, 1)

    # Let's assign BUILDER role to test_user
    _assign_role(Role.objects.get(uid="BUILDER"))

    # Now test_user has BUILDER role and can edit the text_field
    _update_row_with_field_value(text_field, "builder")
    _create_row_with_field_value(text_field, "builder")

    rows, _ = _import_rows_with_field_value(text_field, "builder")
    assert len(rows) == 1
    assert getattr(rows[0], text_field.db_column) == "builder"

    FieldPermissionsHandler.update_field_permissions(user, text_field, "ADMIN")

    # Builders cannot edit/create rows with the text_field anymore
    with pytest.raises(PermissionDenied):
        _update_row_with_field_value(text_field, "admin")

    with pytest.raises(PermissionDenied):
        _create_row_with_field_value(text_field, "admin")

    rows, _ = _import_rows_with_field_value(text_field, "admin")
    assert len(rows) == 1
    assert getattr(rows[0], text_field.db_column) is None

    # they can still edit other fields
    _update_row_with_field_value(number_field, 2)
    _create_row_with_field_value(number_field, 2)

    # Let's assign ADMIN role to test_user
    _assign_role(Role.objects.get(uid="ADMIN"))

    _update_row_with_field_value(text_field, "admin")
    _create_row_with_field_value(text_field, "admin")

    rows, _ = _import_rows_with_field_value(text_field, "admin")
    assert len(rows) == 1
    assert getattr(rows[0], text_field.db_column) == "admin"

    # Now no one is allowed to edit the text_field
    FieldPermissionsHandler.update_field_permissions(user, text_field, "NOBODY")

    with pytest.raises(PermissionDenied):
        _update_row_with_field_value(text_field, "nobody")

    with pytest.raises(PermissionDenied):
        _create_row_with_field_value(text_field, "nobody")

    rows, _ = _import_rows_with_field_value(text_field, "nobody")
    assert len(rows) == 1
    assert getattr(rows[0], text_field.db_column) is None


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_fields_with_permissions_can_be_excluded_from_forms(
    api_client, enterprise_data_fixture, synced_roles
):
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(
        table=table, name="text", primary=True
    )
    number_field = enterprise_data_fixture.create_number_field(
        table=table, name="number`"
    )
    model = table.get_model()
    form = enterprise_data_fixture.create_form_view(
        table=table, public=True, slug="a_public_slug"
    )
    enterprise_data_fixture.create_form_view_field_option(
        form, text_field, enabled=True, order=1, name="text"
    )
    enterprise_data_fixture.create_form_view_field_option(
        form, number_field, enabled=True, order=2, name="number"
    )

    enterprise_data_fixture.enable_enterprise()

    # With the default permissions, everything works the same as before
    FieldPermissionsHandler.update_field_permissions(user, text_field, "EDITOR")

    url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
    rsp = api_client.get(url, format="json")
    assert rsp.status_code == HTTP_200_OK
    rsp_json = rsp.json()
    assert len(rsp_json["fields"]) == 2
    assert rsp_json["fields"][0]["field"]["id"] == text_field.id
    assert rsp_json["fields"][1]["field"]["id"] == number_field.id

    # Also submit a value for the text field works
    rsp = api_client.post(
        url,
        format="json",
        data={text_field.db_column: "some text", number_field.db_column: 1},
    )
    assert rsp.status_code == HTTP_200_OK
    submitted_row_id = rsp.json()["row_id"]
    submitted_row = model.objects.get(id=submitted_row_id)
    assert getattr(submitted_row, text_field.db_column) == "some text"
    assert getattr(submitted_row, number_field.db_column) == 1

    for i, role in enumerate(["BUILDER", "ADMIN", "NOBODY"]):
        FieldPermissionsHandler.update_field_permissions(
            user, text_field, role, allow_in_forms=False
        )

        url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
        rsp = api_client.get(url, format="json")
        assert rsp.status_code == HTTP_200_OK
        rsp_json = rsp.json()

        # The field is no longer present in the form
        assert len(rsp_json["fields"]) == 1
        assert rsp_json["fields"][0]["field"]["id"] == number_field.id

        # It's still possible to submit a value for other fields, but it will be ignored
        rsp = api_client.post(
            url,
            format="json",
            data={text_field.db_column: "some other text", number_field.db_column: i},
        )
        assert rsp.status_code == HTTP_200_OK
        submitted_row_id = rsp.json()["row_id"]
        submitted_row = model.objects.get(id=submitted_row_id)
        # The text field is ignored, only the number field is submitted
        assert getattr(submitted_row, text_field.db_column) is None
        assert getattr(submitted_row, number_field.db_column) == i

    # But if even nobody can change the data, it's not possible to submit a value
    # via a form if the setting is enabled
    FieldPermissionsHandler.update_field_permissions(
        user, text_field, "NOBODY", allow_in_forms=True
    )
    rsp = api_client.post(
        url,
        format="json",
        data={text_field.db_column: "nobody can edit me", number_field.db_column: 10},
    )
    assert rsp.status_code == HTTP_200_OK
    submitted_row_id = rsp.json()["row_id"]
    submitted_row = model.objects.get(id=submitted_row_id)
    assert getattr(submitted_row, text_field.db_column) == "nobody can edit me"
    assert getattr(submitted_row, number_field.db_column) == 10


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_if_license_expires_field_permissions_are_ignored(
    enterprise_data_fixture, synced_roles
):
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    enterprise_data_fixture.enable_enterprise()
    model = table.get_model()

    (row,) = RowHandler().force_create_rows(user, table, [{}], model=model).created_rows

    def _assign_role(role):
        RoleAssignmentHandler().assign_role(
            subject=user,
            workspace=database.workspace,
            role=role,
            scope=database,
        )

    def _create_row_with_field_value(field, value):
        RowHandler().create_rows(
            user=user,
            table=table,
            rows_values=[{field.db_column: value}],
            model=model,
        )

    def _update_row_with_field_value(field, value):
        RowHandler().update_rows(
            user=user,
            table=table,
            rows_values=[{"id": row.id, field.db_column: value}],
            model=model,
        )

    def _import_rows_with_field_value(field, value):
        return RowHandler().import_rows(
            user=user,
            table=table,
            data=[[value]],
            configuration=None,
            validate=False,
        )

    FieldPermissionsHandler.update_field_permissions(user, text_field, "NOBODY")

    with pytest.raises(PermissionDenied):
        _update_row_with_field_value(text_field, "nobody")

    with pytest.raises(PermissionDenied):
        _create_row_with_field_value(text_field, "nobody")

    rows, _ = _import_rows_with_field_value(text_field, "nobody")
    assert len(rows) == 1
    assert getattr(rows[0], text_field.db_column) is None

    enterprise_data_fixture.delete_all_licenses()

    _update_row_with_field_value(text_field, "nobody")
    _create_row_with_field_value(text_field, "nobody")

    rows, _ = _import_rows_with_field_value(text_field, "nobody")
    assert len(rows) == 1
    assert getattr(rows[0], text_field.db_column) == "nobody"
