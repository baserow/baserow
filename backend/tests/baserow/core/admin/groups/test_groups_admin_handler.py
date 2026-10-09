from unittest.mock import patch

from django.db import connection
from django.test.utils import override_settings

import pytest

from baserow.contrib.database.models import Database, Table
from baserow.core.admin.workspaces.exceptions import CannotDeleteATemplateGroupError
from baserow.core.admin.workspaces.handler import WorkspacesAdminHandler
from baserow.core.exceptions import IsNotAdminError
from baserow.core.models import Workspace, WorkspaceUser


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow.core.signals.workspace_deleted.send")
def test_delete_workspace(send_mock, data_fixture):
    staff_user = data_fixture.create_user(is_staff=True)
    normal_user = data_fixture.create_user(is_staff=False)
    other_user = data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace(user=other_user)
    database = data_fixture.create_database_application(workspace=workspace_1)
    table = data_fixture.create_database_table(database=database)

    handler = WorkspacesAdminHandler()

    with pytest.raises(IsNotAdminError):
        handler.delete_workspace(normal_user, workspace_1)

    handler.delete_workspace(staff_user, workspace_1)

    send_mock.assert_called_once()
    assert send_mock.call_args[1]["workspace"].id == workspace_1.id
    assert "user" not in send_mock.call_args[1]
    assert len(send_mock.call_args[1]["workspace_users"]) == 1
    assert send_mock.call_args[1]["workspace_users"][0].id == other_user.id

    assert Database.objects.all().count() == 0
    assert Table.objects.all().count() == 0
    assert f"database_table_{table.id}" not in connection.introspection.table_names()
    assert Workspace.objects.all().count() == 0
    assert WorkspaceUser.objects.all().count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow.core.signals.workspace_deleted.send")
def test_cant_delete_template_workspace(send_mock, data_fixture):
    staff_user = data_fixture.create_user(is_staff=True)
    workspace_1 = data_fixture.create_workspace(user=staff_user)
    database = data_fixture.create_database_application(workspace=workspace_1)
    data_fixture.create_database_table(database=database)

    data_fixture.create_template(workspace=workspace_1)

    handler = WorkspacesAdminHandler()

    with pytest.raises(CannotDeleteATemplateGroupError):
        handler.delete_workspace(staff_user, workspace_1)

    send_mock.assert_not_called()
    assert Workspace.objects.all().count() == 1
