import pytest

from baserow.core.handler import CoreHandler
from baserow.core.last_viewed.handler import LastViewedHandler
from baserow.core.last_viewed.models import UserLastViewedItem
from baserow.core.models import WorkspaceUser
from baserow.core.trash.handler import TrashHandler


def _item_keys():
    return set(UserLastViewedItem.objects.values_list("item_type", "item_id"))


@pytest.mark.django_db
def test_rows_removed_when_view_permanently_deleted(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)
    other_view = data_fixture.create_grid_view(table=table)
    LastViewedHandler.mark_viewed(user.id, "database_view", view.id)
    LastViewedHandler.mark_viewed(user.id, "database_view", other_view.id)

    TrashHandler.trash(user, workspace, database, view)
    assert _item_keys() == {
        ("database_view", view.id),
        ("database_view", other_view.id),
    }

    TrashHandler.permanently_delete(view)
    assert _item_keys() == {("database_view", other_view.id)}


@pytest.mark.django_db
def test_rows_removed_when_table_permanently_deleted(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    other_table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)
    other_view = data_fixture.create_grid_view(table=other_table)
    LastViewedHandler.mark_viewed(user.id, "database_view", view.id)
    LastViewedHandler.mark_viewed(user.id, "database_view", other_view.id)

    TrashHandler.trash(user, workspace, database, table)
    TrashHandler.permanently_delete(table)

    assert _item_keys() == {("database_view", other_view.id)}


@pytest.mark.django_db
def test_rows_removed_when_page_permanently_deleted(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    other_page = data_fixture.create_builder_page(builder=builder)
    LastViewedHandler.mark_viewed(user.id, "builder_page", page.id)
    LastViewedHandler.mark_viewed(user.id, "builder_page", other_page.id)

    TrashHandler.trash(user, workspace, builder, page)
    TrashHandler.permanently_delete(page)

    assert _item_keys() == {("builder_page", other_page.id)}


@pytest.mark.django_db
def test_rows_removed_when_workflow_permanently_deleted(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(automation=automation)
    other_workflow = data_fixture.create_automation_workflow(automation=automation)
    LastViewedHandler.mark_viewed(user.id, "automation_workflow", workflow.id)
    LastViewedHandler.mark_viewed(user.id, "automation_workflow", other_workflow.id)

    TrashHandler.trash(user, workspace, automation, workflow)
    TrashHandler.permanently_delete(workflow)

    assert _item_keys() == {("automation_workflow", other_workflow.id)}


@pytest.mark.django_db
def test_rows_removed_by_cascade_when_application_permanently_deleted(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    LastViewedHandler.mark_viewed(user.id, "dashboard", dashboard.id)
    LastViewedHandler.mark_viewed(user.id, "builder_page", page.id)

    TrashHandler.trash(user, workspace, None, dashboard)
    TrashHandler.permanently_delete(dashboard)

    assert _item_keys() == {("builder_page", page.id)}


@pytest.mark.django_db
def test_rows_removed_by_cascade_when_workspace_permanently_deleted(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    other_workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    other_dashboard = data_fixture.create_dashboard_application(
        workspace=other_workspace
    )
    LastViewedHandler.mark_viewed(user.id, "database_view", view.id)
    LastViewedHandler.mark_viewed(user.id, "dashboard", dashboard.id)
    LastViewedHandler.mark_viewed(user.id, "dashboard", other_dashboard.id)

    TrashHandler.trash(user, workspace, None, workspace)
    TrashHandler.permanently_delete(workspace)

    assert _item_keys() == {("dashboard", other_dashboard.id)}


@pytest.mark.django_db
def test_rows_removed_by_cascade_when_user_deleted(data_fixture):
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(users=[user, other_user])
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    LastViewedHandler.mark_viewed(user.id, "dashboard", dashboard.id)
    LastViewedHandler.mark_viewed(other_user.id, "dashboard", dashboard.id)

    user.delete()

    assert list(UserLastViewedItem.objects.values_list("user_id", flat=True)) == [
        other_user.id
    ]


@pytest.mark.django_db
def test_rows_removed_when_user_is_removed_from_workspace(data_fixture):
    admin = data_fixture.create_user()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[user])
    other_workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    other_dashboard = data_fixture.create_dashboard_application(
        workspace=other_workspace
    )
    LastViewedHandler.mark_viewed(user.id, "dashboard", dashboard.id)
    LastViewedHandler.mark_viewed(admin.id, "dashboard", dashboard.id)
    LastViewedHandler.mark_viewed(user.id, "dashboard", other_dashboard.id)

    CoreHandler().delete_workspace_user(
        admin, WorkspaceUser.objects.get(user=user, workspace=workspace)
    )

    assert set(UserLastViewedItem.objects.values_list("user_id", "item_id")) == {
        (admin.id, dashboard.id),
        (user.id, other_dashboard.id),
    }
