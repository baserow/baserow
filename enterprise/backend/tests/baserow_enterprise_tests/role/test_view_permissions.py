from django.test import override_settings

import pytest

from baserow.contrib.database.views.handler import ViewHandler
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
