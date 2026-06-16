import pytest

from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.pages.trash_types import PageTrashableItemType
from baserow.core.models import TrashEntry


@pytest.mark.django_db
def test_page_trashable_get_parent(data_fixture):
    page = data_fixture.create_builder_page()

    result = PageTrashableItemType().get_parent(page)

    assert result == page.builder


@pytest.mark.django_db
def test_page_trashable_get_name(data_fixture):
    page = data_fixture.create_builder_page(name="My Page")

    result = PageTrashableItemType().get_name(page)

    assert result == f"My Page ({page.id})"


@pytest.mark.django_db
def test_page_trashable_get_name_shared_page_uses_builder_name(data_fixture):
    builder = data_fixture.create_builder_application(name="My Builder")
    shared_page = builder.shared_page

    result = PageTrashableItemType().get_name(shared_page)

    assert result == f"My Builder ({shared_page.id})"


def make_trash_entry(user, page):
    return TrashEntry.objects.create(
        user_who_trashed=user,
        workspace=page.builder.workspace,
        application=page.builder,
        trash_item_type=PageTrashableItemType.type,
        trash_item_id=page.id,
        name=PageTrashableItemType().get_name(page),
        names=PageTrashableItemType().get_names(page),
    )


@pytest.mark.django_db
def test_page_trashable_trash(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder)

    trash_entry = make_trash_entry(user, page)
    result = PageTrashableItemType().trash(page, user, trash_entry)

    assert result is None
    page.refresh_from_db()
    assert page.trashed is True


@pytest.mark.django_db
def test_page_trashable_restore(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder)

    trash_entry = make_trash_entry(user, page)
    PageTrashableItemType().trash(page, user, trash_entry)
    page.refresh_from_db()
    assert page.trashed is True

    result = PageTrashableItemType().restore(page, trash_entry)

    assert result is None
    page.refresh_from_db()
    assert page.trashed is False


@pytest.mark.django_db
def test_page_trashable_permanently_delete_item(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder)
    page_id = page.id

    trash_entry = make_trash_entry(user, page)
    PageTrashableItemType().trash(page, user, trash_entry)
    PageTrashableItemType().permanently_delete_item(page)

    assert Page.objects.filter(id=page_id).count() == 0


def test_page_trashable_get_restore_operation_type():
    result = PageTrashableItemType().get_restore_operation_type()

    assert result == "builder.page.restore"
