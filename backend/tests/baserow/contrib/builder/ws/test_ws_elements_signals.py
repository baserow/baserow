from unittest.mock import patch

import pytest

from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.elements.service import ElementService
from baserow.core.graph.types import GraphPointPosition


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.builder.ws.element.signals.broadcast_to_permitted_users")
def test_element_created(mock_broadcast_to_permitted_users, data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    element = ElementService().create_element(
        user=user,
        element_type=element_type_registry.get("heading"),
        page=page,
    )

    mock_broadcast_to_permitted_users.delay.assert_called_once()
    args = mock_broadcast_to_permitted_users.delay.call_args
    assert args[0][4]["type"] == "element_created"
    assert args[0][4]["element"]["id"] == element.id
    assert args[0][4]["element"]["level"] == 1


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.builder.ws.element.signals.broadcast_to_permitted_users")
def test_element_updated(mock_broadcast_to_permitted_users, data_fixture):
    user = data_fixture.create_user()
    element = data_fixture.create_builder_heading_element(user=user)

    ElementService().update_element(user=user, element=element, level=3)

    mock_broadcast_to_permitted_users.delay.assert_called_once()
    args = mock_broadcast_to_permitted_users.delay.call_args

    assert args[0][4]["type"] == "element_updated"
    assert args[0][4]["element"]["id"] == element.id
    assert args[0][4]["element"]["level"] == 3


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.builder.ws.element.signals.broadcast_to_permitted_users")
def test_element_deleted(mock_broadcast_to_permitted_users, data_fixture):
    user = data_fixture.create_user()
    element = data_fixture.create_builder_heading_element(user=user)

    ElementService().delete_element(user=user, element=element)

    mock_broadcast_to_permitted_users.delay.assert_called_once()
    args = mock_broadcast_to_permitted_users.delay.call_args

    assert args[0][4]["type"] == "element_deleted"
    assert args[0][4]["element_id"] == element.id
    assert args[0][4]["element_ids"] == [element.id]
    assert args[0][4]["page_id"] == element.page_id
    # The relinked graph is sent so other clients re-stitch the page.
    assert "graph" in args[0][4]


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.builder.ws.element.signals.broadcast_to_permitted_users")
def test_element_deleted_container_includes_descendants_and_graph(
    mock_broadcast_to_permitted_users, data_fixture
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    container = ElementService().create_element(
        user=user,
        element_type=element_type_registry.get("column"),
        page=page,
    )
    child = ElementService().create_element(
        user=user,
        element_type=element_type_registry.get("heading"),
        page=page,
        reference_element_id=container.id,
        position=GraphPointPosition.CHILD,
        place_in_container="0",
    )

    mock_broadcast_to_permitted_users.delay.reset_mock()
    ElementService().delete_element(user=user, element=container)

    payload = mock_broadcast_to_permitted_users.delay.call_args[0][4]
    assert payload["type"] == "element_deleted"
    assert payload["element_id"] == container.id
    # The child's record is removed on other clients too.
    assert set(payload["element_ids"]) == {container.id, child.id}
    # Neither the container nor its child remains in the relinked graph.
    assert str(container.id) not in payload["graph"]
    assert str(child.id) not in payload["graph"]


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.builder.ws.element.signals.broadcast_to_permitted_users")
def test_element_moved_same_page(mock_broadcast_to_permitted_users, data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)
    element2 = data_fixture.create_builder_heading_element(page=page)
    element3 = data_fixture.create_builder_heading_element(page=page)

    # Reorder within the same page: move element1 to the south of element3.
    ElementService().move_element(
        user,
        page,
        element1,
        element1.place_in_container,
        element3.id,
        GraphPointPosition.SOUTH,
    )

    mock_broadcast_to_permitted_users.delay.assert_called_once()
    payload = mock_broadcast_to_permitted_users.delay.call_args[0][4]

    assert payload["type"] == "element_moved"
    assert payload["page_id"] == page.id
    assert "graph" in payload
    # A same-page move carries no cross-page relocation fields.
    assert "source_page_id" not in payload
    assert "source_graph" not in payload
    assert "elements" not in payload


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.builder.ws.element.signals.broadcast_to_permitted_users")
def test_element_moved_cross_page(mock_broadcast_to_permitted_users, data_fixture):
    user = data_fixture.create_user()
    page1 = data_fixture.create_builder_page(user=user)
    page2 = data_fixture.create_builder_page(builder=page1.builder)
    element = data_fixture.create_builder_heading_element(page=page1)

    # Move the element from page1 to page2 (cross-page).
    ElementService().move_element(
        user,
        page2,
        element,
        element.place_in_container,
        None,
        GraphPointPosition.SOUTH,
    )

    mock_broadcast_to_permitted_users.delay.assert_called_once()
    payload = mock_broadcast_to_permitted_users.delay.call_args[0][4]

    assert payload["type"] == "element_moved"
    assert payload["page_id"] == page2.id
    assert payload["source_page_id"] == page1.id
    # The target graph contains the moved element; the source graph no longer does.
    assert str(element.id) in payload["graph"]
    assert str(element.id) not in payload["source_graph"]
    # The moved element is serialized so the target page can render it.
    assert [e["id"] for e in payload["elements"]] == [element.id]
    assert payload["elements"][0]["page_id"] == page2.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.builder.ws.element.signals.broadcast_to_permitted_users")
def test_elements_created_includes_workflow_actions(
    mock_broadcast_to_permitted_users, data_fixture
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    data_fixture.create_notification_workflow_action(page=page, element=element)

    ElementService().duplicate_element(user=user, element=element)

    mock_broadcast_to_permitted_users.delay.assert_called_once()
    payload = mock_broadcast_to_permitted_users.delay.call_args[0][4]

    assert payload["type"] == "elements_created"
    assert len(payload["elements"]) == 1
    assert len(payload["workflow_actions"]) == 1
    assert payload["workflow_actions"][0]["element_id"] == payload["elements"][0]["id"]
