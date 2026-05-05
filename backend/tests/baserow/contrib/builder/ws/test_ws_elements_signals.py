from unittest.mock import patch

import pytest

from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.elements.service import ElementService


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
    assert args[0][4]["page_id"] == element.page_id
