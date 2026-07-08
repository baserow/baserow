import pytest

from baserow.core.models import TrashEntry
from baserow.core.user_sources.models import UserSource
from baserow.core.user_sources.operations import RestoreUserSourceOperationType
from baserow.core.user_sources.trash_types import UserSourceTrashableItemType


def make_trash_entry(user, user_source):
    return TrashEntry.objects.create(
        user_who_trashed=user,
        workspace=user_source.application.workspace,
        application=user_source.application,
        trash_item_type=UserSourceTrashableItemType.type,
        trash_item_id=user_source.id,
        name=UserSourceTrashableItemType().get_name(user_source),
        names=UserSourceTrashableItemType().get_names(user_source),
    )


@pytest.mark.django_db
def test_user_source_trashable_get_parent(data_fixture):
    user_source = data_fixture.create_user_source_with_first_type()

    result = UserSourceTrashableItemType().get_parent(user_source)

    assert result == user_source.application


@pytest.mark.django_db
def test_user_source_trashable_get_name(data_fixture):
    user_source = data_fixture.create_user_source_with_first_type(name="My User Source")

    result = UserSourceTrashableItemType().get_name(user_source)

    assert result == f"My User Source ({user_source.id})"


@pytest.mark.django_db
def test_user_source_trashable_trash(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(
        application=application, user=user
    )

    trash_entry = make_trash_entry(user, user_source)
    result = UserSourceTrashableItemType().trash(user_source, user, trash_entry)

    assert result is None
    user_source.refresh_from_db()
    assert user_source.trashed is True


@pytest.mark.django_db
def test_user_source_trashable_restore(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(
        application=application, user=user
    )

    trash_entry = make_trash_entry(user, user_source)
    UserSourceTrashableItemType().trash(user_source, user, trash_entry)
    user_source.refresh_from_db()
    assert user_source.trashed is True

    result = UserSourceTrashableItemType().restore(user_source, trash_entry)

    assert result is None
    user_source.refresh_from_db()
    assert user_source.trashed is False


@pytest.mark.django_db
def test_user_source_trashable_permanently_delete_item(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(
        application=application, user=user
    )
    user_source_id = user_source.id

    trash_entry = make_trash_entry(user, user_source)
    UserSourceTrashableItemType().trash(user_source, user, trash_entry)
    UserSourceTrashableItemType().permanently_delete_item(user_source)

    assert UserSource.objects_and_trash.filter(id=user_source_id).count() == 0


def test_user_source_trashable_get_restore_operation_type():
    result = UserSourceTrashableItemType().get_restore_operation_type()

    assert result == RestoreUserSourceOperationType.type
