import pytest

from baserow.contrib.database.views.last_viewed_types import (
    DatabaseViewLastViewedItemType,
)
from baserow.core.registries import last_viewed_item_type_registry
from baserow.core.trash.handler import TrashHandler


def test_type_is_registered():
    assert isinstance(
        last_viewed_item_type_registry.get("database_view"),
        DatabaseViewLastViewedItemType,
    )


@pytest.mark.django_db
def test_get_queryset_for_user_only_returns_views_the_user_can_open(data_fixture):
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)
    trashed_view = data_fixture.create_grid_view(table=table)
    trashed_table = data_fixture.create_database_table(database=database)
    view_of_trashed_table = data_fixture.create_grid_view(table=trashed_table)
    trashed_database = data_fixture.create_database_application(workspace=workspace)
    view_of_trashed_database = data_fixture.create_grid_view(
        table=data_fixture.create_database_table(database=trashed_database)
    )
    trashed_workspace = data_fixture.create_workspace(user=user)
    view_of_trashed_workspace = data_fixture.create_grid_view(
        table=data_fixture.create_database_table(
            database=data_fixture.create_database_application(
                workspace=trashed_workspace
            )
        )
    )

    TrashHandler.trash(user, workspace, database, trashed_view)
    TrashHandler.trash(user, workspace, database, trashed_table)
    TrashHandler.trash(user, workspace, None, trashed_database)
    TrashHandler.trash(user, trashed_workspace, None, trashed_workspace)

    item_type = DatabaseViewLastViewedItemType()

    def ids(queryset):
        return set(queryset.values_list("id", flat=True))

    assert ids(item_type.get_queryset_for_user(user.id)) == {view.id}
    assert ids(item_type.get_queryset_for_user(other_user.id)) == set()
    for excluded in (
        trashed_view,
        view_of_trashed_table,
        view_of_trashed_database,
        view_of_trashed_workspace,
    ):
        assert excluded.id not in ids(item_type.get_queryset_for_user(user.id))

    # Trashed views still exist, so their rows are not stale until they are
    # permanently deleted.
    assert ids(item_type.get_existing_item_ids_queryset()) >= {
        view.id,
        trashed_view.id,
    }


@pytest.mark.django_db
def test_get_parent_ids(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table)

    item_type = DatabaseViewLastViewedItemType()
    instance = item_type.get_queryset_for_user(user.id).get(id=view.id)
    assert item_type.get_application_id(instance) == database.id
    assert item_type.get_workspace_id(instance) == workspace.id


@pytest.mark.django_db
def test_get_item_ids_of_permanently_deleted(data_fixture):
    table = data_fixture.create_database_table()
    view_1 = data_fixture.create_grid_view(table=table)
    view_2 = data_fixture.create_grid_view(table=table)
    other_view = data_fixture.create_grid_view()
    item_type = DatabaseViewLastViewedItemType()

    assert list(item_type.get_item_ids_of_permanently_deleted("view", view_1)) == [
        view_1.id
    ]
    # A permanently deleted table cascades to its views without a signal per view.
    assert set(item_type.get_item_ids_of_permanently_deleted("table", table)) == {
        view_1.id,
        view_2.id,
    }
    assert other_view.id not in item_type.get_item_ids_of_permanently_deleted(
        "table", table
    )
    assert list(item_type.get_item_ids_of_permanently_deleted("row", table)) == []
