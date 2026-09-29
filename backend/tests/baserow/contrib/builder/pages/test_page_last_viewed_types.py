import pytest

from baserow.contrib.builder.pages.last_viewed_types import (
    BuilderPageLastViewedItemType,
)
from baserow.core.registries import last_viewed_item_type_registry
from baserow.core.trash.handler import TrashHandler


def test_type_is_registered():
    assert isinstance(
        last_viewed_item_type_registry.get("builder_page"),
        BuilderPageLastViewedItemType,
    )


@pytest.mark.django_db
def test_get_queryset_for_user_only_returns_pages_the_user_can_open(data_fixture):
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    shared_page = data_fixture.create_builder_page(builder=builder, shared=True)
    trashed_page = data_fixture.create_builder_page(builder=builder)
    trashed_builder = data_fixture.create_builder_application(workspace=workspace)
    page_of_trashed_builder = data_fixture.create_builder_page(builder=trashed_builder)
    trashed_workspace = data_fixture.create_workspace(user=user)
    page_of_trashed_workspace = data_fixture.create_builder_page(
        builder=data_fixture.create_builder_application(workspace=trashed_workspace)
    )

    TrashHandler.trash(user, workspace, builder, trashed_page)
    TrashHandler.trash(user, workspace, None, trashed_builder)
    TrashHandler.trash(user, trashed_workspace, None, trashed_workspace)

    item_type = BuilderPageLastViewedItemType()
    assert set(item_type.get_queryset_for_user(user.id)) == {page}
    assert list(item_type.get_queryset_for_user(other_user.id)) == []
    assert shared_page not in item_type.get_queryset_for_user(user.id)
    assert page_of_trashed_builder not in item_type.get_queryset_for_user(user.id)
    assert page_of_trashed_workspace not in item_type.get_queryset_for_user(user.id)

    # Trashed pages still exist, so their rows are not stale until they are
    # permanently deleted.
    assert set(item_type.get_existing_item_ids_queryset()) >= {page, trashed_page}


@pytest.mark.django_db
def test_get_parent_ids(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    item_type = BuilderPageLastViewedItemType()
    instance = item_type.get_queryset_for_user(user.id).get(id=page.id)
    assert item_type.get_application_id(instance) == builder.id
    assert item_type.get_workspace_id(instance) == workspace.id


@pytest.mark.django_db
def test_get_item_ids_of_permanently_deleted(data_fixture):
    page = data_fixture.create_builder_page()
    item_type = BuilderPageLastViewedItemType()

    assert list(
        item_type.get_item_ids_of_permanently_deleted("builder_page", page)
    ) == [page.id]
    assert (
        list(item_type.get_item_ids_of_permanently_deleted("application", page.builder))
        == []
    )
