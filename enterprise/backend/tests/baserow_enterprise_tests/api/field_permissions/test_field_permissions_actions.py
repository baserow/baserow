from django.test.utils import override_settings

import pytest

from baserow.contrib.database.action.scopes import TableActionScopeType
from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.registries import action_type_registry
from baserow.test_utils.helpers import assert_undo_redo_actions_are_valid
from baserow_enterprise.field_permissions.actions import (
    FieldPermissionUpdated,
    UpdateFieldPermissionsActionType,
)
from baserow_enterprise.field_permissions.handler import FieldPermissionsHandler
from baserow_enterprise.field_permissions.models import (
    FieldPermissions,
    FieldPermissionsRoleEnum,
)
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
    assert not FieldPermissions.objects.filter(field=field).exists()
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


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_can_undo_redo_specific_field_permission_subjects(
    enterprise_data_fixture, enable_enterprise, synced_roles
):
    session_id = "session-id"
    user = enterprise_data_fixture.create_user(session_id=session_id)
    first_member = enterprise_data_fixture.create_user()
    second_member = enterprise_data_fixture.create_user()
    table = enterprise_data_fixture.create_database_table(name="Car", user=user)
    workspace = table.database.workspace
    for member in [first_member, second_member]:
        enterprise_data_fixture.create_user_workspace(
            user=member, workspace=workspace, permissions="EDITOR"
        )
    field = enterprise_data_fixture.create_text_field(table=table)

    first_subjects = [{"subject_id": first_member.id, "subject_type": "auth.User"}]
    second_subjects = [{"subject_id": second_member.id, "subject_type": "auth.User"}]
    FieldPermissionsHandler.update_field_permissions(
        user, field, FieldPermissionsRoleEnum.CUSTOM, subjects=first_subjects
    )

    action_type_registry.get_by_type(UpdateFieldPermissionsActionType).do(
        user,
        field,
        role=FieldPermissionsRoleEnum.CUSTOM.value,
        subjects=second_subjects,
    )
    assert (
        FieldPermissionsHandler._get_field_permission_subject_identifiers(field)
        == second_subjects
    )
    action = Action.objects.filter(type=UpdateFieldPermissionsActionType.type).latest(
        "id"
    )
    assert action.params["original_subjects"] == first_subjects
    assert action.params["subjects"] == second_subjects

    undone_actions = ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )
    assert undone_actions[0].error is None
    assert (
        FieldPermissionsHandler._get_field_permission_subject_identifiers(field)
        == first_subjects
    )

    ActionHandler.redo(
        user, [TableActionScopeType.value(table_id=table.id)], session_id
    )
    assert (
        FieldPermissionsHandler._get_field_permission_subject_identifiers(field)
        == second_subjects
    )
