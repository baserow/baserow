from django.contrib.contenttypes.models import ContentType
from django.test import override_settings

import pytest

from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import View
from baserow.core.exceptions import PermissionDenied
from baserow_enterprise.role.handler import RoleAssignmentHandler


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_form_view_as_editor_fails(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = enterprise_data_fixture.create_database_table(user)
    form = enterprise_data_fixture.create_form_view(table=table)
    editor_role = RoleAssignmentHandler().get_role_by_uid("EDITOR")
    RoleAssignmentHandler().assign_role(
        user, table.database.workspace, role=editor_role, scope=table
    )

    handler = ViewHandler()

    with pytest.raises(PermissionDenied):
        handler.update_view(user=user, view=form, name="Test 1")


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_form_view_notification_as_editor_succeeds(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = enterprise_data_fixture.create_database_table(user)
    form = enterprise_data_fixture.create_form_view(table=table)
    editor_role = RoleAssignmentHandler().get_role_by_uid("EDITOR")
    RoleAssignmentHandler().assign_role(
        user, table.database.workspace, role=editor_role, scope=table
    )

    handler = ViewHandler()
    handler.update_view(user=user, view=form, receive_notification_on_submit=True)
    assert form.users_to_notify_on_submit.count() == 1


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_form_view_and_notification_as_editor_fails(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = enterprise_data_fixture.create_database_table(user)
    form = enterprise_data_fixture.create_form_view(table=table)
    editor_role = RoleAssignmentHandler().get_role_by_uid("EDITOR")
    RoleAssignmentHandler().assign_role(
        user, table.database.workspace, role=editor_role, scope=table
    )

    handler = ViewHandler()

    with pytest.raises(PermissionDenied):
        handler.update_view(
            user=user, view=form, receive_notification_on_submit=True, name="Test"
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_duplicate_view_and_remember_role(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    user2 = enterprise_data_fixture.create_user(
        email="test2@test.nl", password="password", first_name="Test1"
    )
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    grid = enterprise_data_fixture.create_grid_view(table=table)
    view = View.objects.get(pk=grid.id)
    admin_role = RoleAssignmentHandler().get_role_by_uid("ADMIN")
    editor_role = RoleAssignmentHandler().get_role_by_uid("EDITOR")
    RoleAssignmentHandler().assign_role(
        user, workspace, role=admin_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=editor_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(user2, workspace, role=admin_role, scope=view)

    handler = ViewHandler()
    duplicated_grid = handler.duplicate_view(user, grid)
    duplicated_view = View.objects.get(pk=duplicated_grid.id)

    role_assignments = RoleAssignmentHandler().get_role_assignments(
        workspace, duplicated_view
    )
    assert len(role_assignments) == 1
    assert role_assignments[0].workspace_id == workspace.id
    assert role_assignments[0].subject_id == user2.id
    assert role_assignments[0].scope_id == duplicated_view.id
    assert (
        role_assignments[0].scope_type_id == ContentType.objects.get_for_model(View).id
    )
