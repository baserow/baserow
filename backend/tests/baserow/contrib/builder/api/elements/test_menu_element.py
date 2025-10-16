import uuid

from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import MenuItemElement
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.types import BASEROW_FORMULA_MODE_SIMPLE
from baserow.test_utils.helpers import AnyInt, AnyStr


@pytest.fixture
def menu_element_fixture(data_fixture):
    """Fixture to help test the Menu element."""

    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page_a = data_fixture.create_builder_page(builder=builder, path="/page_a/:foo/")
    page_b = data_fixture.create_builder_page(builder=builder, path="/page_b/")

    menu_element = data_fixture.create_builder_menu_element(user=user, page=page_a)

    return {
        "token": token,
        "page_a": page_a,
        "page_b": page_b,
        "menu_element": menu_element,
    }


def create_menu_item(**kwargs):
    menu_item = {
        "name": "Link",
        "type": MenuItemElement.TYPES.LINK,
        "variant": MenuItemElement.VARIANTS.LINK,
        "menu_item_order": 0,
        "uid": uuid.uuid4(),
        "navigation_type": "",
        "navigate_to_page_id": None,
        "navigate_to_url": "",
        "page_parameters": [],
        "query_parameters": [],
        "parent_menu_item": None,
        "target": "self",
        "children": [],
    }
    menu_item.update(kwargs)
    return menu_item


@pytest.mark.django_db
def test_get_menu_element(api_client, menu_element_fixture):
    menu_element = menu_element_fixture["menu_element"]

    # Add a Menu item
    menu_item = create_menu_item()
    data = {"menu_items": [menu_item]}
    ElementHandler().update_element(menu_element, **data)

    page = menu_element_fixture["page_a"]
    token = menu_element_fixture["token"]

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    [menu] = response.json()

    assert menu["id"] == menu_element.id
    assert menu["type"] == "menu"
    assert menu["orientation"] == "horizontal"
    assert menu["menu_items"] == [
        {
            "children": [],
            "id": menu_element.menu_items.all()[0].id,
            "menu_item_order": AnyInt(),
            "name": "Link",
            "navigate_to_page_id": None,
            "navigate_to_url": BaserowFormulaObject(
                formula="",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "navigation_type": "",
            "page_parameters": [],
            "parent_menu_item": None,
            "query_parameters": [],
            "target": "self",
            "type": "link",
            "uid": AnyStr(),
            "variant": "link",
        },
    ]


@pytest.mark.django_db
def test_create_menu_element(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})

    response = api_client.post(
        url,
        {
            "type": "menu",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["type"] == "menu"


@pytest.mark.django_db
def test_can_update_menu_element_items(api_client, menu_element_fixture):
    menu_element = menu_element_fixture["menu_element"]
    token = menu_element_fixture["token"]

    url = reverse("api:builder:element:item", kwargs={"element_id": menu_element.id})
    response = api_client.patch(
        url,
        {
            "menu_items": [
                {
                    "name": "Foo Bar",
                    "variant": "link",
                    "value": "",
                    "type": "link",
                    "uid": uuid.uuid4(),
                    "children": [],
                    "navigation_type": "page",
                    "navigate_to_page_id": None,
                    "navigate_to_url": "",
                    "page_parameters": [],
                    "query_parameters": [],
                    "target": "self",
                }
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["id"] == menu_element.id
    assert data["menu_items"] == [
        {
            "id": menu_element.menu_items.all()[0].id,
            "menu_item_order": AnyInt(),
            "name": "Foo Bar",
            "variant": "link",
            "type": "link",
            "uid": AnyStr(),
            "navigate_to_page_id": None,
            "navigate_to_url": BaserowFormulaObject(
                version=BASEROW_FORMULA_VERSION_INITIAL,
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                formula="",
            ),
            "navigation_type": "page",
            "page_parameters": [],
            "parent_menu_item": None,
            "query_parameters": [],
            "target": "self",
            "children": [],
        },
    ]
