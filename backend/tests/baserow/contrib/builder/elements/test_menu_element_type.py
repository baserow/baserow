import json
import uuid
from collections import defaultdict
from copy import deepcopy

import pytest

from baserow.contrib.builder.api.elements.serializers import MenuItemSerializer
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import MenuElement, MenuItemElement
from baserow.contrib.builder.workflow_actions.models import NotificationWorkflowAction
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.types import BASEROW_FORMULA_MODE_SIMPLE
from baserow.core.utils import MirrorDict
from baserow.test_utils.helpers import AnyInt


@pytest.fixture
def menu_element_fixture(data_fixture):
    """Fixture to help test the Menu element."""

    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page_a = data_fixture.create_builder_page(builder=builder, path="/page_a/:foo/")
    page_b = data_fixture.create_builder_page(builder=builder, path="/page_b/")

    menu_element = data_fixture.create_builder_menu_element(user=user, page=page_a)

    return {
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

    data = {
        "orientation": orientation,
        "menu_items": [],
    }
    updated_menu_element = ElementHandler().update_element(menu_element, **data)

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
def test_add_menu_item(menu_element_fixture, name, item_type, variant):
    menu_element = menu_element_fixture["menu_element"]

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
    updated_menu_element = ElementHandler().update_element(menu_element, **data)

    assert updated_menu_element.menu_items.count() == 1
    menu_item = updated_menu_element.menu_items.first()
    assert menu_item.variant == variant
    assert menu_item.type == item_type
    assert menu_item.name == name
    assert menu_item.menu_item_order == AnyInt()
    assert menu_item.uid == uid
    assert menu_item.parent_menu_item is None


@pytest.mark.django_db
def test_add_sub_link(menu_element_fixture):
    menu_element = menu_element_fixture["menu_element"]

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
    updated_menu_element = ElementHandler().update_element(menu_element, **data)

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
        (
            "navigate_to_url",
            BaserowFormulaObject(
                formula="https://www.baserow.io",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
        ),
        (
            "page_parameters",
            [
                {
                    "name": "foo",
                    "value": BaserowFormulaObject(
                        formula="'bar'",
                        mode=BASEROW_FORMULA_MODE_SIMPLE,
                        version=BASEROW_FORMULA_VERSION_INITIAL,
                    ),
                }
            ],
        ),
        (
            "query_parameters",
            [
                {
                    "name": "param",
                    "value": BaserowFormulaObject(
                        formula="'baz'",
                        mode=BASEROW_FORMULA_MODE_SIMPLE,
                        version=BASEROW_FORMULA_VERSION_INITIAL,
                    ),
                }
            ],
        ),
        ("target", "_blank"),
    ],
)
def test_update_menu_item(menu_element_fixture, field, value):
    menu_element = menu_element_fixture["menu_element"]

    assert menu_element.menu_items.count() == 0

    uid = uuid.uuid4()

    if field == "navigate_to_page_id":
        value = menu_element_fixture["page_b"].id

    menu_item = {
        "name": "Page",
        "type": MenuItemElement.TYPES.LINK.value,
        "variant": MenuItemElement.VARIANTS.LINK.value,
        "menu_item_order": 0,
        "uid": str(uid),
        "navigation_type": "page",
        "navigate_to_page_id": None,
        "navigate_to_url": {
            "formula": "",
            "mode": BASEROW_FORMULA_MODE_SIMPLE,
            "version": BASEROW_FORMULA_VERSION_INITIAL,
        },
        "parent_menu_item": None,
        "page_parameters": [],
        "query_parameters": [],
        "target": "self",
        "children": [],
    }

    expected = deepcopy(menu_item)
    expected[field] = value
    expected["id"] = AnyInt()
    expected["menu_item_order"] = AnyInt()

    # Create the initial Menu item
    data = {"menu_items": [menu_item]}
    ElementHandler().update_element(menu_element, **data)

    # Update a specific field
    menu_item[field] = value
    updated_menu_element = ElementHandler().update_element(menu_element, **data)

    item = updated_menu_element.menu_items.first()
    updated_menu_item = MenuItemSerializer(item).data

    # Ensure that only that specific field was updated
    assert updated_menu_item == expected


@pytest.mark.django_db
def test_workflow_action_removed_when_menu_item_deleted(
    menu_element_fixture, data_fixture
):
    menu_element = menu_element_fixture["menu_element"]

    uid = uuid.uuid4()
    menu_item = {
        "name": "Greet",
        "type": MenuItemElement.TYPES.BUTTON,
        "menu_item_order": 0,
        "uid": uid,
        "children": [],
    }
    data = {"menu_items": [menu_item]}
    ElementHandler().update_element(menu_element, **data)

    data_fixture.create_workflow_action(
        NotificationWorkflowAction,
        page=menu_element_fixture["page_a"],
        element=menu_element,
        event=f"{uid}_click",
    )
    assert NotificationWorkflowAction.objects.count() == 1

    # Delete the field
    data = {"menu_items": []}
    updated_menu_element = ElementHandler().update_element(menu_element, **data)

    assert updated_menu_element.menu_items.exists() is False

    assert NotificationWorkflowAction.objects.count() == 0


@pytest.mark.django_db
def test_specific_workflow_action_removed_when_menu_item_deleted(
    menu_element_fixture, data_fixture
):
    menu_element = menu_element_fixture["menu_element"]

    uid_1 = uuid.uuid4()
    uid_2 = uuid.uuid4()
    menu_item_1 = {
        "name": "Greet 1",
        "type": MenuItemElement.TYPES.BUTTON,
        "menu_item_order": 0,
        "uid": uid_1,
        "children": [],
    }
    menu_item_2 = {
        "name": "Greet 2",
        "type": MenuItemElement.TYPES.BUTTON,
        "menu_item_order": 0,
        "uid": uid_2,
        "children": [],
    }
    data = {"menu_items": [menu_item_1, menu_item_2]}
    updated_menu_element = ElementHandler().update_element(menu_element, **data)
    assert updated_menu_element.menu_items.count() == 2

    for uid in [uid_1, uid_2]:
        data_fixture.create_workflow_action(
            NotificationWorkflowAction,
            page=menu_element_fixture["page_a"],
            element=menu_element,
            event=f"{uid}_click",
        )

    assert NotificationWorkflowAction.objects.count() == 2

    # Delete the first menu item
    data = {"menu_items": [menu_item_2]}
    updated_menu_element = ElementHandler().update_element(menu_element, **data)

    assert updated_menu_element.menu_items.count() == 1

    # Ensure only the Notification for the first menu item exists
    assert NotificationWorkflowAction.objects.filter(element=menu_element).count() == 1
    assert (
        NotificationWorkflowAction.objects.filter(element=menu_element).first().event
        == f"{uid_2}_click"
    )


@pytest.mark.django_db
def test_all_workflow_actions_removed_when_menu_element_deleted(
    menu_element_fixture, data_fixture
):
    menu_element = menu_element_fixture["menu_element"]

    uid_1 = uuid.uuid4()
    uid_2 = uuid.uuid4()
    menu_item_1 = {
        "name": "Greet 1",
        "type": MenuItemElement.TYPES.BUTTON,
        "menu_item_order": 0,
        "uid": uid_1,
        "children": [],
    }
    menu_item_2 = {
        "name": "Greet 2",
        "type": MenuItemElement.TYPES.BUTTON,
        "menu_item_order": 0,
        "uid": uid_2,
        "children": [],
    }
    data = {"menu_items": [menu_item_1, menu_item_2]}
    updated_menu_element = ElementHandler().update_element(menu_element, **data)

    for uid in [uid_1, uid_2]:
        data_fixture.create_workflow_action(
            NotificationWorkflowAction,
            page=menu_element_fixture["page_a"],
            element=menu_element,
            event=f"{uid}_click",
        )

    assert updated_menu_element.menu_items.count() == 2
    assert NotificationWorkflowAction.objects.count() == 2

    # Delete the Menu element, which will cascade delete all menu items
    ElementHandler().delete_element(menu_element)

    # There should be no Menu Element, Menu items, or Notifications remaining
    assert MenuElement.objects.count() == 0
    assert MenuItemElement.objects.count() == 0
    assert NotificationWorkflowAction.objects.count() == 0


@pytest.mark.django_db
def test_import_export(menu_element_fixture, data_fixture):
    page = menu_element_fixture["page_a"]
    menu_element = menu_element_fixture["menu_element"]

    # Create a Menu Element with Menu items.
    uid_1 = uuid.uuid4()
    uid_2 = uuid.uuid4()
    uid_3 = uuid.uuid4()
    uid_4 = uuid.uuid4()
    menu_item_1 = {
        "name": "Greet",
        "type": MenuItemElement.TYPES.BUTTON,
        "menu_item_order": 0,
        "uid": uid_1,
        "children": [],
    }
    menu_item_2 = {
        "name": "Link A",
        "type": MenuItemElement.TYPES.LINK,
        "menu_item_order": 1,
        "uid": uid_2,
        "children": [],
    }
    menu_item_3 = {
        "name": "Sublinks",
        "type": MenuItemElement.TYPES.LINK,
        "menu_item_order": 2,
        "uid": uid_3,
        "children": [
            {
                "name": "Sublink A",
                "type": MenuItemElement.TYPES.LINK,
                "menu_item_order": 3,
                "uid": uid_4,
                "navigate_to_page_id": page.id,
            }
        ],
    }

    data = {"menu_items": [menu_item_1, menu_item_2, menu_item_3]}
    ElementHandler().update_element(menu_element, **data)

    menu_element_type = menu_element.get_type()

    # Export the Menu element and ensure there are no Menu elements
    # after deleting it.
    exported = menu_element_type.export_serialized(menu_element)
    assert json.dumps(exported)

    ElementHandler().delete_element(menu_element)

    assert MenuElement.objects.count() == 0
    assert MenuItemElement.objects.count() == 0

    # After importing the Menu element the menu items should be correctly
    # imported as well.
    id_mapping = defaultdict(MirrorDict)
    menu_element_type.import_serialized(page, exported, id_mapping)

    menu_element = MenuElement.objects.first()

    # Ensure the Menu Items have been imported correctly
    # and uids should have been updated
    button_item = menu_element.menu_items.get(name="Greet")
    assert button_item.type == MenuItemElement.TYPES.BUTTON
    assert button_item.uid != uid_1

    link_item = menu_element.menu_items.get(name="Link A")
    assert link_item.type == MenuItemElement.TYPES.LINK
    assert link_item.uid != uid_2

    sublinks_item = menu_element.menu_items.get(name="Sublinks")
    assert sublinks_item.uid != uid_3

    sublink_a = menu_element.menu_items.get(name="Sublink A")
    assert sublink_a.uid != uid_4


@pytest.mark.django_db
def test_delete_duplicated_menu_doesnt_affect_initial_element(
    menu_element_fixture, data_fixture
):
    menu_element = menu_element_fixture["menu_element"]

    # Create a Menu Element with Menu items.
    uid_1 = uuid.uuid4()
    menu_item_1 = {
        "name": "Greet",
        "type": MenuItemElement.TYPES.BUTTON,
        "menu_item_order": 0,
        "uid": uid_1,
        "children": [],
    }

    data = {"menu_items": [menu_item_1]}
    ElementHandler().update_element(menu_element, **data)

    workflow_action = data_fixture.create_workflow_action(
        NotificationWorkflowAction,
        page=menu_element.page,
        element=menu_element,
        event=f"{uid_1}_click",
    )

    duplicated = ElementHandler().duplicate_element(menu_element)

    element = duplicated["elements"][0]
    duplicated_workflow_action = duplicated["workflow_actions"][0]

    duplicated_workflow_action.event != workflow_action.event

    assert NotificationWorkflowAction.objects.count() == 2

    ElementHandler().delete_element(element)

    # We want to make sure that deleting the clone doesn't delete the initial event
    assert NotificationWorkflowAction.objects.count() == 1
    assert NotificationWorkflowAction.objects.first().event == workflow_action.event
