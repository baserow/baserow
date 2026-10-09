from datetime import datetime, timezone

import pytest
from freezegun import freeze_time

from baserow.contrib.database.models import Database
from baserow.core.models import Workspace, WorkspaceUser


@pytest.mark.django_db
def test_created_and_updated_on_mixin():
    with freeze_time("2020-01-01 12:00"):
        workspace = Workspace.objects.create(name="Workspace")

    assert workspace.created_on == datetime(2020, 1, 1, 12, 00, tzinfo=timezone.utc)
    assert workspace.updated_on == datetime(2020, 1, 1, 12, 00, tzinfo=timezone.utc)

    with freeze_time("2020-01-02 12:00"):
        workspace.name = "Workspace2"
        workspace.save()

    assert workspace.created_on == datetime(2020, 1, 1, 12, 00, tzinfo=timezone.utc)
    assert workspace.updated_on == datetime(2020, 1, 2, 12, 00, tzinfo=timezone.utc)


@pytest.mark.django_db
def test_workspace_user_get_next_order(data_fixture):
    user = data_fixture.create_user()

    assert WorkspaceUser.get_last_order(user) == 1

    workspace_user_1 = data_fixture.create_user_workspace(order=0)
    workspace_user_2_1 = data_fixture.create_user_workspace(order=10)
    data_fixture.create_user_workspace(user=workspace_user_2_1.user, order=11)

    assert WorkspaceUser.get_last_order(workspace_user_1.user) == 1
    assert WorkspaceUser.get_last_order(workspace_user_2_1.user) == 12


@pytest.mark.django_db
def test_application_content_type_init(data_fixture):
    workspace = data_fixture.create_workspace()
    database = Database.objects.create(name="Test 1", order=0, workspace=workspace)

    assert database.content_type.app_label == "database"
    assert database.content_type.model == "database"


@pytest.mark.django_db
def test_core_models_hierarchy(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    app = data_fixture.create_database_application(workspace=workspace, name="Test 1")

    assert app.get_parent() == app.application_ptr
    assert app.get_root() == workspace

    assert workspace.get_parent() is None
    assert workspace.get_root() == workspace
