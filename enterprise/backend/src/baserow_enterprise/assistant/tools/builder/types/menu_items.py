"""Menu items as Kuma reads and changes them."""

import uuid
from collections import defaultdict
from collections.abc import Iterable
from operator import attrgetter
from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

from pydantic import Field, field_validator, model_validator

from baserow_enterprise.assistant.types import BaseModel

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


MENU_ITEM_NAME_MAX_LENGTH = 225


def _refuse_blank(name: str) -> str:
    if not name.strip():
        raise ValueError("A menu item name can't be blank.")
    return name


class MenuItemAdd(BaseModel):
    """A new menu item linking to a page."""

    name: str = Field(
        ...,
        max_length=MENU_ITEM_NAME_MAX_LENGTH,
        description="Display text. It must differ from the names of the items at its level.",
    )
    page_id: int = Field(
        ..., description="Target page ID, a page of this application from list_pages."
    )
    parent_uid: str | None = Field(
        default=None,
        description="Add it as a sub-link of this top-level link (uid from list_elements). Omit for a top-level item.",
    )
    before_uid: str | None = Field(
        default=None,
        description="Insert before this item at the same level (uid from list_elements). Omit to add it last.",
    )

    @field_validator("name")
    @classmethod
    def _name_is_not_blank(cls, name: str) -> str:
        return _refuse_blank(name)


class MenuItemUpdate(BaseModel):
    """A change to one existing menu item. Keys you omit keep their current value."""

    uid: str = Field(..., description="The item's uid, from list_elements.")
    name: str | None = Field(
        default=None,
        max_length=MENU_ITEM_NAME_MAX_LENGTH,
        description="New display text.",
    )
    page_id: int | None = Field(
        default=None,
        description="(link) Point the link to this page of this application, from list_pages. Buttons can't link to a page.",
    )

    @field_validator("name")
    @classmethod
    def _name_is_not_blank(cls, name: str | None) -> str | None:
        return name if name is None else _refuse_blank(name)

    @model_validator(mode="after")
    def _require_a_change(self) -> "MenuItemUpdate":
        if self.name is None and self.page_id is None:
            raise ValueError(f"Menu item {self.uid} needs a new name or page_id.")
        return self


class RemovedMenuItem(TypedDict):
    """A menu item an update removed."""

    uid: str
    name: str
    type: str
    deleted_click_actions: NotRequired[int]


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
