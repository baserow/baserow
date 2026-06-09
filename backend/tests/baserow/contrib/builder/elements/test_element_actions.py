import uuid

import pytest

from baserow.contrib.builder.action_scopes import (
    PageActionScopeType,
    SharedPageActionScopeType,
)
from baserow.contrib.builder.elements.actions import (
    CreateElementActionType,
    DeleteElementActionType,
    DuplicateElementActionType,
    MoveElementActionType,
    UpdateElementActionType,
)
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.core.action.handler import ActionHandler


def _next_id(page, element_id):
    # The graph handler is cached per page id within the test process and mutated
    # in place by the action's do/undo/redo, so reading it back reflects the
    # current state without re-fetching from the database. Returns the id of the
    # element directly after ``element_id`` on the default edge.
    return page.get_graph().graph[str(element_id)]["next"][""][0]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_element_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    heading_type = element_type_registry.get("heading")

    element = CreateElementActionType.do(user, heading_type, page, {})

    assert Element.objects.filter(id=element.id).exists()
    assert str(element.id) in page.get_graph().graph

    ActionHandler.undo(user, [PageActionScopeType.value(page.id)], session_id)

    element.refresh_from_db(fields=["trashed"])
    assert element.trashed
    assert str(element.id) not in page.get_graph().graph

    ActionHandler.redo(user, [PageActionScopeType.value(page.id)], session_id)

    element.refresh_from_db(fields=["trashed"])
    assert not element.trashed
    assert str(element.id) in page.get_graph().graph


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_element_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_heading_element(page=page, level=1)

    UpdateElementActionType.do(user, element, {"level": 3})

    element.refresh_from_db()
    assert element.level == 3

    ActionHandler.undo(user, [PageActionScopeType.value(page.id)], session_id)

    element.refresh_from_db()
    assert element.level == 1

    ActionHandler.redo(user, [PageActionScopeType.value(page.id)], session_id)

    element.refresh_from_db()
    assert element.level == 3


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_delete_element_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_heading_element(page=page)

    DeleteElementActionType.do(user, element)

    element.refresh_from_db(fields=["trashed"])
    assert element.trashed
    assert str(element.id) not in page.get_graph().graph

    ActionHandler.undo(user, [PageActionScopeType.value(page.id)], session_id)

    element.refresh_from_db(fields=["trashed"])
    assert not element.trashed
    assert str(element.id) in page.get_graph().graph

    ActionHandler.redo(user, [PageActionScopeType.value(page.id)], session_id)

    element.refresh_from_db(fields=["trashed"])
    assert element.trashed


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_duplicate_element_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_heading_element(page=page)

    result = DuplicateElementActionType.do(user, element)
    duplicated = result["elements"][0]

    assert duplicated.id != element.id
    assert Element.objects.filter(id=duplicated.id).exists()

    ActionHandler.undo(user, [PageActionScopeType.value(page.id)], session_id)

    duplicated.refresh_from_db(fields=["trashed"])
    assert duplicated.trashed
    # The source element is untouched.
    element.refresh_from_db(fields=["trashed"])
    assert not element.trashed

    ActionHandler.redo(user, [PageActionScopeType.value(page.id)], session_id)

    duplicated.refresh_from_db(fields=["trashed"])
    assert not duplicated.trashed


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_move_element_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    first = data_fixture.create_builder_heading_element(page=page)
    second = data_fixture.create_builder_heading_element(page=page)
    third = data_fixture.create_builder_heading_element(page=page)

    # Initial chain: first -> second -> third.
    assert _next_id(page, first.id) == second.id

    # Move third to be south of first: first -> third -> second.
    MoveElementActionType.do(
        user,
        third,
        page,
        "",
        first.id,
        "south",
    )

    assert _next_id(page, first.id) == third.id

    ActionHandler.undo(user, [PageActionScopeType.value(page.id)], session_id)

    assert _next_id(page, first.id) == second.id

    ActionHandler.redo(user, [PageActionScopeType.value(page.id)], session_id)

    assert _next_id(page, first.id) == third.id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_shared_element_action_is_scoped_to_shared_page(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    builder = data_fixture.create_builder_application(user=user)
    content_page = data_fixture.create_builder_page(builder=builder)
    shared_page = builder.shared_page
    header_type = element_type_registry.get("header")

    # A header element lives on the builder's shared page.
    element = CreateElementActionType.do(user, header_type, shared_page, {})
    assert Element.objects.filter(id=element.id).exists()

    # The content page scope alone must NOT undo a shared element's action.
    ActionHandler.undo(user, [PageActionScopeType.value(content_page.id)], session_id)
    element.refresh_from_db(fields=["trashed"])
    assert not element.trashed

    # The shared page scope (sent by the editor alongside the content page) does.
    ActionHandler.undo(
        user, [SharedPageActionScopeType.value(shared_page.id)], session_id
    )
    element.refresh_from_db(fields=["trashed"])
    assert element.trashed

    ActionHandler.redo(
        user, [SharedPageActionScopeType.value(shared_page.id)], session_id
    )
    element.refresh_from_db(fields=["trashed"])
    assert not element.trashed
