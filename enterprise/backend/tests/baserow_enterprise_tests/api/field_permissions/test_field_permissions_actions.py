from django.test.utils import override_settings

import pytest

from baserow.contrib.database.action.scopes import TableActionScopeType
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.test_utils.helpers import assert_undo_redo_actions_are_valid
from baserow_enterprise.field_permissions.actions import (
    FieldPermissionUpdated,
    UpdateFieldPermissionsActionType,
)
from baserow_enterprise.field_permissions.handler import FieldPermissionsHandler
from baserow_enterprise.field_permissions.models import FieldPermissionsRoleEnum
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.mark.django_db()
@override_settings(DEBUG=True)
def test_can_undo_updating_field_permissions(
    enterprise_data_fixture, enable_enterprise, synced_roles
):
    session_id = "session-id"
    user = enterprise_data_fixture.create_user(session_id=session_id)
    table = enterprise_data_fixture.create_database_table(name="Car", user=user)
    field = enterprise_data_fixture.create_text_field(table=table)
    editor_role = Role.objects.get(uid="BUILDER")
    RoleAssignmentHandler().assign_role(
        subject=user, workspace=table.database.workspace, role=editor_role, scope=table
    )

    original_permissions = FieldPermissionsHandler.get_field_permissions(user, field)
    assert original_permissions.role == FieldPermissionsRoleEnum.EDITOR.value
    assert original_permissions.allow_in_forms is True

    field_permissions: FieldPermissionUpdated = action_type_registry.get_by_type(
        UpdateFieldPermissionsActionType
    ).do(user, field, role=FieldPermissionsRoleEnum.ADMIN.value, allow_in_forms=False)

    assert field_permissions.role == FieldPermissionsRoleEnum.ADMIN.value
    assert field_permissions.allow_in_forms is False
    assert field_permissions.can_write_values is False

    action_undone = ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    assert_undo_redo_actions_are_valid(
        action_undone, [UpdateFieldPermissionsActionType]
    )

    undone_field_permissions = FieldPermissionsHandler.get_field_permissions(
        user, field
    )
    assert undone_field_permissions.role == FieldPermissionsRoleEnum.EDITOR.value
    assert undone_field_permissions.allow_in_forms is True


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_can_undo_redo_updating_field_permissions(
    enterprise_data_fixture, enable_enterprise, synced_roles
):
    session_id = "session-id"
    user = enterprise_data_fixture.create_user(session_id=session_id)
    table = enterprise_data_fixture.create_database_table(name="Car", user=user)
    field = enterprise_data_fixture.create_text_field(table=table)
    editor_role = Role.objects.get(uid="BUILDER")
    RoleAssignmentHandler().assign_role(
        subject=user, workspace=table.database.workspace, role=editor_role, scope=table
    )

    original_permissions = FieldPermissionsHandler.get_field_permissions(user, field)
    assert original_permissions.id is None
    assert original_permissions.role == FieldPermissionsRoleEnum.EDITOR.value
    assert original_permissions.allow_in_forms is True

    field_permissions: FieldPermissionUpdated = action_type_registry.get_by_type(
        UpdateFieldPermissionsActionType
    ).do(user, field, role=FieldPermissionsRoleEnum.ADMIN.value, allow_in_forms=False)

    assert field_permissions.role == FieldPermissionsRoleEnum.ADMIN.value
    assert field_permissions.allow_in_forms is False
    assert field_permissions.can_write_values is False

    ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    action_redone = ActionHandler.redo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )

    assert_undo_redo_actions_are_valid(
        action_redone, [UpdateFieldPermissionsActionType]
    )

    redone_field_permissions = FieldPermissionsHandler.get_field_permissions(
        user, field
    )
    assert redone_field_permissions.role == FieldPermissionsRoleEnum.ADMIN.value
    assert redone_field_permissions.allow_in_forms is False
