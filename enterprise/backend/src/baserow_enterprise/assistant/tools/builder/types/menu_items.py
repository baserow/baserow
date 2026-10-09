"""Menu items as Kuma reads and changes them."""

import uuid
from collections import defaultdict
from collections.abc import Iterable
from operator import attrgetter
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

if TYPE_CHECKING:
    from baserow.contrib.builder.elements.models import MenuElement, MenuItemElement


class ListedMenuItem(TypedDict):
    """One menu item as the model reads it."""

    uid: str
    name: str
    type: str
    page_id: int | None


class ListedTopLevelMenuItem(ListedMenuItem):
    """A top-level menu item as the model reads it, with its sub-links."""

    children: NotRequired[list[ListedMenuItem]]


def new_menu_link(name: str, page_id: int) -> dict[str, Any]:
    """
    Return the values of a new menu item that links to a page.

    :param name: The item's display text.
    :param page_id: The page the item links to.
    :return: The values, keyed like a menu's ``menu_items`` input.
    """

    return {
        "uid": str(uuid.uuid4()),
        "type": "link",
        "variant": "link",
        "name": name,
        "navigation_type": "page",
        "navigate_to_page_id": page_id,
        "target": "self",
    }


def group_menu_items(
    items: Iterable["MenuItemElement"],
) -> tuple[list["MenuItemElement"], defaultdict[int, list["MenuItemElement"]]]:
    """
    Split a menu's items into its top-level items and the sub-links of each.

    :param items: All the items of one menu.
    :return: The top-level items and the sub-links by parent id, in menu order.
    """

    top_level = []
    sub_links = defaultdict(list)
    for item in sorted(items, key=attrgetter("menu_item_order")):
        if item.parent_menu_item_id is None:
            top_level.append(item)
        else:
            sub_links[item.parent_menu_item_id].append(item)
    return top_level, sub_links


def _listed(item: "MenuItemElement") -> ListedMenuItem:
    return ListedMenuItem(
        uid=str(item.uid),
        name=item.name,
        type=item.type,
        page_id=item.navigate_to_page_id,
    )


def listed_menu_items(menu: "MenuElement") -> list[ListedTopLevelMenuItem]:
    """
    Describe a menu's items with the uids Kuma changes them by.

    :param menu: The menu element.
    :return: The top-level items in order, each with its sub-links as children.
    """

    top_level, sub_links = group_menu_items(menu.menu_items.all())
    items = []
    for item in top_level:
        listed = ListedTopLevelMenuItem(**_listed(item))
        if sub_links[item.id]:
            listed["children"] = [_listed(sub_link) for sub_link in sub_links[item.id]]
        items.append(listed)
    return items
