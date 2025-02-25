import uuid

import pytest

from baserow.contrib.builder.elements.models import MenuElement, MenuItemElement
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.elements.service import ElementService
from baserow.test_utils.helpers import AnyInt


@pytest.fixture
def menu_element_fixture(data_fixture):
    """Fixture to help test the Menu element."""

    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page_a = data_fixture.create_builder_page(builder=builder, path="/page_a/:foo/")
    page_b = data_fixture.create_builder_page(builder=builder, path="/page_b/")

    ElementService().create_element(
        user,
        element_type_registry.get("menu"),
        page=page_a,
    )

    menu_element = MenuElement.objects.last()

    return {
        "user": user,
        "page_a": page_a,
        "page_b": page_b,
        "menu_element": menu_element,
    }


@pytest.mark.django_db
def test_create_menu_element(menu_element_fixture):
    menu_element = menu_element_fixture["menu_element"]

    assert menu_element.menu_items.count() == 0
    assert menu_element.orientation == MenuElement.ORIENTATIONS.HORIZONTAL


@pytest.mark.django_db
@pytest.mark.parametrize(
    "orientation",
    [
        MenuElement.ORIENTATIONS.HORIZONTAL,
        MenuElement.ORIENTATIONS.VERTICAL,
    ],
)
def test_update_menu_element(menu_element_fixture, orientation):
    menu_element = menu_element_fixture["menu_element"]
    user = menu_element_fixture["user"]

    data = {
        "orientation": orientation,
        "menu_items": [],
    }
    updated_menu_element = ElementService().update_element(user, menu_element, **data)

    assert updated_menu_element.menu_items.count() == 0
    assert updated_menu_element.orientation == orientation


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name,item_type,variant",
    [
        (
            "Page 1",
            MenuItemElement.TYPES.LINK,
            MenuItemElement.VARIANTS.LINK,
        ),
        (
            "Page 2",
            MenuItemElement.TYPES.LINK,
            MenuItemElement.VARIANTS.BUTTON,
        ),
        (
            "Click me",
            MenuItemElement.TYPES.BUTTON,
            "",
        ),
        (
            "",
            MenuItemElement.TYPES.SEPARATOR,
            "",
        ),
        (
            "",
            MenuItemElement.TYPES.SPACER,
            "",
        ),
    ],
)
def test_add_root_level_menu_item(menu_element_fixture, name, item_type, variant):
    menu_element = menu_element_fixture["menu_element"]
    user = menu_element_fixture["user"]

    assert menu_element.menu_items.count() == 0

    uid = uuid.uuid4()
    data = {
        "menu_items": [
            {
                "variant": variant,
                "type": item_type,
                "uid": uid,
                "name": name,
                "children": [],
            }
        ]
    }
    updated_menu_element = ElementService().update_element(user, menu_element, **data)

    assert updated_menu_element.menu_items.count() == 1
    menu_item = updated_menu_element.menu_items.first()
    assert menu_item.variant == variant
    assert menu_item.type == item_type
    assert menu_item.name == name
    assert menu_item.menu_item_order == AnyInt()
    assert menu_item.uid == uid
    assert menu_item.parent_menu_item is None


@pytest.mark.django_db
def test_sub_link_to_menu_item(menu_element_fixture):
    menu_element = menu_element_fixture["menu_element"]
    user = menu_element_fixture["user"]

    assert menu_element.menu_items.count() == 0

    parent_uid = uuid.uuid4()
    child_uid = uuid.uuid4()

    data = {
        "menu_items": [
            {
                "name": "Click for more links",
                "type": MenuItemElement.TYPES.LINK,
                "variant": MenuItemElement.VARIANTS.LINK,
                "menu_item_order": 0,
                "uid": parent_uid,
                "navigation_type": "page",
                "navigate_to_page_id": None,
                "navigate_to_url": "",
                "page_parameters": [],
                "query_parameters": [],
                "parent_menu_item": None,
                "target": "self",
                "children": [
                    {
                        "name": "Sublink",
                        "type": MenuItemElement.TYPES.LINK,
                        "variant": MenuItemElement.VARIANTS.LINK,
                        "uid": child_uid,
                    }
                ],
            }
        ]
    }
    updated_menu_element = ElementService().update_element(user, menu_element, **data)

    # Both parent and child are MenuItemElement instances
    assert updated_menu_element.menu_items.count() == 2

    parent_item = updated_menu_element.menu_items.get(uid=parent_uid)
    assert parent_item.parent_menu_item is None
    assert parent_item.uid == parent_uid

    child_item = updated_menu_element.menu_items.get(uid=child_uid)
    assert child_item.parent_menu_item == parent_item
    assert child_item.uid == child_uid
    assert child_item.type == MenuItemElement.TYPES.LINK
    assert child_item.variant == MenuItemElement.VARIANTS.LINK
    assert child_item.name == "Sublink"
    assert child_item.menu_item_order == AnyInt()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "New Page"),
        ("navigation_type", "link"),
        # None is replaced with a valid page in the test
        ("navigate_to_page_id", None),
        ("navigate_to_url", "https://www.baserow.io"),
        ("page_parameters", [{"name": "foo", "value": "'bar'"}]),
        ("query_parameters", [{"name": "param", "value": "'baz'"}]),
        ("target", "_blank"),
    ],
)
def test_update_parent_item(menu_element_fixture, field, value):
    menu_element = menu_element_fixture["menu_element"]
    user = menu_element_fixture["user"]

    assert menu_element.menu_items.count() == 0

    uid = uuid.uuid4()

    if field == "navigate_to_page_id":
        value = menu_element_fixture["page_b"].id

    menu_item = {
        "name": "Page",
        "type": MenuItemElement.TYPES.LINK,
        "variant": MenuItemElement.VARIANTS.LINK,
        "menu_item_order": 0,
        "uid": uid,
        "navigation_type": "page",
        "navigate_to_page_id": None,
        "navigate_to_url": "",
        "page_parameters": [],
        "query_parameters": [],
        "parent_menu_item": None,
        "target": "self",
        "children": [],
    }

    data = {"menu_items": [menu_item]}
    ElementService().update_element(user, menu_element, **data)

    # Update specific fields
    menu_item[field] = value
    updated_menu_element = ElementService().update_element(user, menu_element, **data)

    item = updated_menu_element.menu_items.first()
    assert getattr(item, field) == value
