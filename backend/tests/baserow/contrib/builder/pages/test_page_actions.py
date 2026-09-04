import uuid

import pytest

from baserow.contrib.builder.pages.actions import (
    CreatePageActionType,
    DeletePageActionType,
    DuplicatePageActionType,
    OrderPagesActionType,
    UpdatePageActionType,
)
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page
from baserow.core.action.handler import ActionHandler
from baserow.core.action.scopes import ApplicationActionScopeType


def _scope(builder):
    return [ApplicationActionScopeType.value(builder.id)]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_page_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    builder = data_fixture.create_builder_application(user=user)

    page = CreatePageActionType.do(user, builder, "New page", "/new-page")

    assert Page.objects.filter(id=page.id).exists()

    ActionHandler.undo(user, _scope(builder), session_id)
    assert not Page.objects.filter(id=page.id).exists()
    assert Page.trash.filter(id=page.id).exists()

    ActionHandler.redo(user, _scope(builder), session_id)
    assert Page.objects.filter(id=page.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_delete_page_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)

    DeletePageActionType.do(user, page)
    assert not Page.objects.filter(id=page.id).exists()
    assert Page.trash.filter(id=page.id).exists()

    ActionHandler.undo(user, _scope(builder), session_id)
    assert Page.objects.filter(id=page.id).exists()

    ActionHandler.redo(user, _scope(builder), session_id)
    assert not Page.objects.filter(id=page.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_page_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder, name="Original")

    page = PageHandler().get_page(page.id)
    UpdatePageActionType.do(user, page, name="Updated")

    page.refresh_from_db()
    assert page.name == "Updated"

    ActionHandler.undo(user, _scope(builder), session_id)
    page.refresh_from_db()
    assert page.name == "Original"

    ActionHandler.redo(user, _scope(builder), session_id)
    page.refresh_from_db()
    assert page.name == "Updated"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_order_pages_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    builder = data_fixture.create_builder_application(user=user)
    data_fixture.create_builder_page(user=user, builder=builder)
    data_fixture.create_builder_page(user=user, builder=builder)
    data_fixture.create_builder_page(user=user, builder=builder)

    def order():
        return list(
            Page.objects_without_shared.filter(builder=builder)
            .order_by("order", "id")
            .values_list("id", flat=True)
        )

    original = order()
    reordered = list(reversed(original))

    OrderPagesActionType.do(user, builder, reordered)
    assert order() == reordered

    ActionHandler.undo(user, _scope(builder), session_id)
    assert order() == original

    ActionHandler.redo(user, _scope(builder), session_id)
    assert order() == reordered


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_duplicate_page_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)

    page_clone = DuplicatePageActionType.do(user, page)
    assert page_clone.id != page.id
    assert Page.objects.filter(id=page_clone.id).exists()

    # Undo trashes the duplicated page but leaves the original intact.
    ActionHandler.undo(user, _scope(builder), session_id)
    assert not Page.objects.filter(id=page_clone.id).exists()
    assert Page.trash.filter(id=page_clone.id).exists()
    assert Page.objects.filter(id=page.id).exists()

    # Redo restores the duplicated page.
    ActionHandler.redo(user, _scope(builder), session_id)
    assert Page.objects.filter(id=page_clone.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_page_create_configure_undo_redo(data_fixture):
    # create -> configure (rename) -> undo -> redo, then undo both -> trashed,
    # then redo both -> restored & configured.
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    builder = data_fixture.create_builder_application(user=user)

    page = CreatePageActionType.do(user, builder, "Original", "/original")

    page = PageHandler().get_page(page.id)
    UpdatePageActionType.do(user, page, name="Configured")
    page.refresh_from_db()
    assert page.name == "Configured"

    ActionHandler.undo(user, _scope(builder), session_id)
    page.refresh_from_db()
    assert page.name == "Original"

    ActionHandler.redo(user, _scope(builder), session_id)
    page.refresh_from_db()
    assert page.name == "Configured"

    # Undo rename + undo create -> trashed.
    ActionHandler.undo(user, _scope(builder), session_id)
    ActionHandler.undo(user, _scope(builder), session_id)
    assert not Page.objects.filter(id=page.id).exists()

    # Redo create (restore) + redo rename.
    ActionHandler.redo(user, _scope(builder), session_id)
    assert Page.objects.filter(id=page.id).exists()
    ActionHandler.redo(user, _scope(builder), session_id)
    page.refresh_from_db()
    assert page.name == "Configured"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_page_grouped_create_configure_undo_redo(data_fixture):
    # The frontend may batch create + configure into one action group.
    session_id = "session-id"
    action_group = uuid.uuid4()
    user = data_fixture.create_user(session_id=session_id, action_group=action_group)
    builder = data_fixture.create_builder_application(user=user)

    page = CreatePageActionType.do(user, builder, "Original", "/original")
    page = PageHandler().get_page(page.id)
    UpdatePageActionType.do(user, page, name="Configured")

    ActionHandler.undo(user, _scope(builder), session_id)
    assert not Page.objects.filter(id=page.id).exists()

    ActionHandler.redo(user, _scope(builder), session_id)
    assert Page.objects.filter(id=page.id).exists()
    page.refresh_from_db()
    assert page.name == "Configured"
