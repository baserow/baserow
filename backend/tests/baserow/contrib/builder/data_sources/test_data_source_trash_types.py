import pytest

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.data_sources.operations import (
    RestoreDataSourceOperationType,
)
from baserow.contrib.builder.data_sources.trash_types import (
    DataSourceTrashableItemType,
)
from baserow.core.models import TrashEntry


def make_trash_entry(user, data_source):
    return TrashEntry.objects.create(
        user_who_trashed=user,
        workspace=data_source.page.builder.workspace,
        application=data_source.page.builder,
        trash_item_type=DataSourceTrashableItemType.type,
        trash_item_id=data_source.id,
        name=DataSourceTrashableItemType().get_name(data_source),
        names=DataSourceTrashableItemType().get_names(data_source),
    )


@pytest.mark.django_db
def test_data_source_trashable_get_parent(data_fixture):
    data_source = data_fixture.create_builder_data_source()

    result = DataSourceTrashableItemType().get_parent(data_source)

    assert result == data_source.page


@pytest.mark.django_db
def test_data_source_trashable_get_name(data_fixture):
    data_source = data_fixture.create_builder_data_source(name="My Data Source")

    result = DataSourceTrashableItemType().get_name(data_source)

    assert result == f"My Data Source ({data_source.id})"


@pytest.mark.django_db
def test_data_source_trashable_trash(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source = data_fixture.create_builder_data_source(page=page)

    trash_entry = make_trash_entry(user, data_source)
    result = DataSourceTrashableItemType().trash(data_source, user, trash_entry)

    assert result is None
    data_source.refresh_from_db()
    assert data_source.trashed is True


@pytest.mark.django_db
def test_data_source_trashable_restore(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source = data_fixture.create_builder_data_source(page=page)

    trash_entry = make_trash_entry(user, data_source)
    DataSourceTrashableItemType().trash(data_source, user, trash_entry)
    data_source.refresh_from_db()
    assert data_source.trashed is True

    result = DataSourceTrashableItemType().restore(data_source, trash_entry)

    assert result is None
    data_source.refresh_from_db()
    assert data_source.trashed is False


@pytest.mark.django_db
def test_data_source_trashable_permanently_delete_item(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source = data_fixture.create_builder_data_source(page=page)
    data_source_id = data_source.id

    trash_entry = make_trash_entry(user, data_source)
    DataSourceTrashableItemType().trash(data_source, user, trash_entry)
    DataSourceTrashableItemType().permanently_delete_item(data_source)

    assert DataSource.objects_and_trash.filter(id=data_source_id).count() == 0


def test_data_source_trashable_get_restore_operation_type():
    result = DataSourceTrashableItemType().get_restore_operation_type()

    assert result == RestoreDataSourceOperationType.type
