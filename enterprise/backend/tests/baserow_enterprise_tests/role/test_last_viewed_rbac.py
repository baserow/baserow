from datetime import datetime, timezone

import pytest

from baserow.contrib.database.views.models import View
from baserow.core.last_viewed.handler import LastViewedHandler
from baserow.core.last_viewed.models import UserLastViewedItem
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_premium.views.models import OWNERSHIP_TYPE_PERSONAL


@pytest.fixture(autouse=True)
def enable_enterprise_for_all_tests_here(enable_enterprise, synced_roles):
    pass


def _record(user, item_type, item, application, workspace, when):
    return UserLastViewedItem.objects.create(
        user=user,
        item_type=item_type,
        item_id=item.id,
        application=application,
        workspace=workspace,
        last_viewed=datetime.fromisoformat(when).replace(tzinfo=timezone.utc),
    )


@pytest.mark.django_db
def test_list_items_excludes_items_the_role_hides(
    data_fixture, enterprise_data_fixture
):
    admin = data_fixture.create_user()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[user])
    no_access = Role.objects.get(uid="NO_ACCESS")

    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)
    hidden_database = data_fixture.create_database_application(workspace=workspace)
    hidden_table = data_fixture.create_database_table(database=hidden_database)
    hidden_view = data_fixture.create_grid_view(table=hidden_table)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    hidden_builder = data_fixture.create_builder_application(workspace=workspace)
    hidden_page = data_fixture.create_builder_page(builder=hidden_builder)

    RoleAssignmentHandler().assign_role(
        user, workspace, role=no_access, scope=hidden_database
    )
    RoleAssignmentHandler().assign_role(
        user, workspace, role=no_access, scope=hidden_builder
    )

    _record(
        user,
        "database_view",
        hidden_view,
        hidden_database,
        workspace,
        "2026-01-04 10:00",
    )
    _record(
        user, "builder_page", hidden_page, hidden_builder, workspace, "2026-01-03 10:00"
    )
    _record(user, "database_view", view, database, workspace, "2026-01-02 10:00")
    _record(user, "builder_page", page, builder, workspace, "2026-01-01 10:00")

    items, has_more = LastViewedHandler.list_items(user, limit=20)

    assert [(item.item_type.type, item.instance.id) for item in items] == [
        ("database_view", view.id),
        ("builder_page", page.id),
    ]
    assert has_more is False

    # The admin is not restricted and sees nothing of the other user's history.
    assert LastViewedHandler.list_items(admin, limit=20) == ([], False)


@pytest.mark.django_db
def test_list_items_excludes_the_personal_views_of_other_users(data_fixture):
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user, members=[other_user])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    collaborative = data_fixture.create_grid_view(table=table)
    own_personal = data_fixture.create_grid_view(
        table=table, owned_by=user, ownership_type=OWNERSHIP_TYPE_PERSONAL
    )
    other_personal = data_fixture.create_grid_view(
        table=table, owned_by=other_user, ownership_type=OWNERSHIP_TYPE_PERSONAL
    )

    _record(
        user, "database_view", other_personal, database, workspace, "2026-01-03 10:00"
    )
    _record(
        user, "database_view", own_personal, database, workspace, "2026-01-02 10:00"
    )
    _record(
        user, "database_view", collaborative, database, workspace, "2026-01-01 10:00"
    )

    items, _ = LastViewedHandler.list_items(user, limit=20)

    assert [item.instance.id for item in items] == [own_personal.id, collaborative.id]


@pytest.mark.django_db
def test_list_items_respects_a_role_on_a_single_table(data_fixture):
    admin = data_fixture.create_user()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[user])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    hidden_table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)
    hidden_view = data_fixture.create_grid_view(table=hidden_table)

    RoleAssignmentHandler().assign_role(
        user, workspace, role=Role.objects.get(uid="NO_ACCESS"), scope=hidden_table
    )

    _record(user, "database_view", hidden_view, database, workspace, "2026-01-02 10:00")
    _record(user, "database_view", view, database, workspace, "2026-01-01 10:00")

    items, _ = LastViewedHandler.list_items(user, limit=20)

    assert [item.instance.id for item in items] == [view.id]


@pytest.mark.django_db
def test_list_items_respects_a_role_on_a_single_view(data_fixture):
    admin = data_fixture.create_user()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[user])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    allowed_view = data_fixture.create_grid_view(table=table)
    hidden_view = data_fixture.create_grid_view(table=table)

    # No access to anything but the one view the user is a viewer of.
    RoleAssignmentHandler().assign_role(
        user, workspace, role=Role.objects.get(uid="NO_ACCESS"), scope=database
    )
    RoleAssignmentHandler().assign_role(
        user,
        workspace,
        role=Role.objects.get(uid="VIEWER"),
        # The scope has to be the base view, not the grid view.
        scope=View.objects.get(pk=allowed_view.id),
    )

    _record(user, "database_view", hidden_view, database, workspace, "2026-01-02 10:00")
    _record(
        user, "database_view", allowed_view, database, workspace, "2026-01-01 10:00"
    )

    items, _ = LastViewedHandler.list_items(user, limit=20)

    assert [item.instance.id for item in items] == [allowed_view.id]
