"""Turn Kuma's menu item changes into the full item list core saves."""

from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any, NamedTuple

from django.db.models import Count

from baserow.contrib.builder.elements.models import MenuElement, MenuItemElement
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow_enterprise.assistant.tools.shared import ToolInputError

from .types.changes import NO_CHANGES, canonical_uid, name_key, unique_in_order
from .types.menu_items import (
    MenuItemAdd,
    MenuItemUpdate,
    RemovedMenuItem,
    group_menu_items,
    new_menu_link,
)

MenuItemValues = dict[str, Any]
SubLinks = defaultdict[int, list[MenuItemElement]]


class MenuItemsChange(NamedTuple):
    """The items to save for a menu, and the saved items they remove."""

    menu_items: list[MenuItemValues]
    removed: list[RemovedMenuItem]


def linkable_page_ids(builder_id: int) -> frozenset[int]:
    """
    Return the pages a menu item of a builder may link to.

    :param builder_id: The builder the menu belongs to.
    :return: The ids of the builder's pages, without its shared and trashed pages.
    """

    return frozenset(
        Page.objects_without_shared.filter(builder_id=builder_id).values_list(
            "id", flat=True
        )
    )


def merge_menu_items(
    menu: MenuElement | None,
    page_ids: frozenset[int],
    add: list[MenuItemAdd],
    update: list[MenuItemUpdate],
    reorder: list[str] | None,
    remove: list[str],
) -> MenuItemsChange:
    """
    Merge menu item changes into the full item list core saves for a menu.

    Items the changes don't name are resent exactly as saved, so they keep their uid,
    settings, sub-links and click actions. Removing a top-level item removes its
    sub-links too. Removals apply first, then updates, the reorder and additions.

    :param menu: The menu, or None when a header or footer has no menu yet.
    :param page_ids: The pages new and updated items may link to.
    :param add: New page links.
    :param update: Changes to existing items, by uid.
    :param reorder: The uids of every top-level item that stays, in the new order, or
        None to keep the saved order.
    :param remove: The uids of the items to delete.
    :return: The items to save, each top-level item with its sub-links as children,
        and the items removed.
    :raises ToolInputError: When a change can't be applied; nothing is saved.
    """

    # Query again: a cached menu can hold items prefetched before they changed.
    saved = list(menu.menu_items.order_by("menu_item_order")) if menu else []
    top_level, sub_links = group_menu_items(saved)
    by_uid = {
        str(item.uid): item
        for parent in top_level
        for item in (parent, *sub_links[parent.id])
    }
    update_uids = [canonical_uid(change.uid) for change in update]
    remove_uids = [canonical_uid(uid) for uid in remove]
    order = [canonical_uid(uid) for uid in reorder] if reorder is not None else None
    anchors = [
        canonical_uid(uid)
        for new in add
        for uid in (new.parent_uid, new.before_uid)
        if uid is not None
    ]

    _check_references(by_uid, [*update_uids, *remove_uids, *(order or []), *anchors])
    _check_pages(page_ids, add, update)
    removed = _with_sub_links(top_level, sub_links, set(remove_uids))
    removed_uids = {str(item.uid) for item in removed}
    _check_changed_once(update_uids, removed_uids, by_uid)
    kept = [item for item in top_level if str(item.uid) not in removed_uids]
    if order is not None:
        _check_order(kept, order, removed_uids, by_uid)
        position = {uid: index for index, uid in enumerate(order)}
        kept.sort(key=lambda item: position[str(item.uid)])
    _check_anchors_stay(anchors, removed_uids, by_uid)

    changes = dict(zip(update_uids, update))
    menu_id = menu.id if menu else None
    merged = [
        {
            **_changed(item, changes.get(str(item.uid)), menu_id),
            "children": [
                _changed(sub_link, changes.get(str(sub_link.uid)), menu_id)
                for sub_link in sub_links[item.id]
                if str(sub_link.uid) not in removed_uids
            ],
        }
        for item in kept
    ]
    for new in add:
        _insert(merged, new, by_uid)

    if merged == _saved_tree(top_level, sub_links):
        raise ToolInputError(
            "No menu item would change: the names and pages you sent are already "
            "saved, and the order is the same. Items you don't list stay as they "
            f"are. {NO_CHANGES}"
        )
    return MenuItemsChange(merged, _removed_items(menu, removed))


def _named(item: MenuItemElement) -> str:
    return f"'{item.name}' (uid {item.uid})"


def _named_list(uids: Iterable[str], by_uid: dict[str, MenuItemElement]) -> str:
    return ", ".join(_named(by_uid[uid]) for uid in uids)


def _listing(by_uid: dict[str, MenuItemElement]) -> str:
    if not by_uid:
        return "The menu has no items yet: add them with add_menu_items."
    return f"Its items are: {_named_list(by_uid, by_uid)}. Use these uids."


def _check_references(by_uid: dict[str, MenuItemElement], uids: list[str]) -> None:
    unknown = unique_in_order(uid for uid in uids if uid not in by_uid)
    if unknown:
        raise ToolInputError(
            f"Menu items {unknown} are not in this menu. {_listing(by_uid)} "
            f"{NO_CHANGES}"
        )


def _check_pages(
    page_ids: frozenset[int], add: list[MenuItemAdd], update: list[MenuItemUpdate]
) -> None:
    sent = [
        *(new.page_id for new in add),
        *(change.page_id for change in update if change.page_id is not None),
    ]
    unknown = unique_in_order(page_id for page_id in sent if page_id not in page_ids)
    if unknown:
        raise ToolInputError(
            f"Pages {unknown} aren't pages of this application. Use list_pages to "
            f"find their ids. {NO_CHANGES}"
        )


def _with_sub_links(
    top_level: list[MenuItemElement], sub_links: SubLinks, uids: set[str]
) -> list[MenuItemElement]:
    removed = []
    for item in top_level:
        if str(item.uid) in uids:
            removed += [item, *sub_links[item.id]]
        else:
            removed += [link for link in sub_links[item.id] if str(link.uid) in uids]
    return removed


def _check_changed_once(
    update_uids: list[str], removed_uids: set[str], by_uid: dict[str, MenuItemElement]
) -> None:
    repeated = [uid for uid, count in Counter(update_uids).items() if count > 1]
    if repeated:
        raise ToolInputError(
            "These menu items are changed more than once: "
            f"{_named_list(repeated, by_uid)}. Put all changes to an item in one "
            f"update_menu_items entry. {NO_CHANGES}"
        )
    both = unique_in_order(uid for uid in update_uids if uid in removed_uids)
    if both:
        raise ToolInputError(
            f"These menu items are changed and removed: {_named_list(both, by_uid)}. "
            f"A removed item's sub-links are removed with it. {NO_CHANGES}"
        )


def _check_order(
    kept: list[MenuItemElement],
    order: list[str],
    removed_uids: set[str],
    by_uid: dict[str, MenuItemElement],
) -> None:
    listed = Counter(order)
    problems = {
        "Missing": [str(item.uid) for item in kept if str(item.uid) not in listed],
        "Listed more than once": [uid for uid, count in listed.items() if count > 1],
        "Removed in this call": [uid for uid in listed if uid in removed_uids],
        "Sub-links, which can't be reordered": [
            uid
            for uid in listed
            if uid not in removed_uids and by_uid[uid].parent_menu_item_id is not None
        ],
    }
    details = "".join(
        f" {problem}: {_named_list(uids, by_uid)}."
        for problem, uids in problems.items()
        if uids
    )
    if details:
        raise ToolInputError(
            "reorder_menu_items must list every top-level item that stays exactly "
            f"once.{details} {NO_CHANGES}"
        )


def _check_anchors_stay(
    anchors: list[str], removed_uids: set[str], by_uid: dict[str, MenuItemElement]
) -> None:
    removed_anchors = unique_in_order(uid for uid in anchors if uid in removed_uids)
    if removed_anchors:
        raise ToolInputError(
            "These menu items are removed in this call, so new items can't go under "
            f"or before them: {_named_list(removed_anchors, by_uid)}. {NO_CHANGES}"
        )


def _saved_values(item: MenuItemElement) -> MenuItemValues:
    return {
        "uid": str(item.uid),
        "type": item.type,
        "variant": item.variant,
        "name": item.name,
        "navigation_type": item.navigation_type,
        "navigate_to_page_id": item.navigate_to_page_id,
        "navigate_to_url": item.navigate_to_url,
        "page_parameters": item.page_parameters,
        "query_parameters": item.query_parameters,
        "target": item.target,
    }


def _saved_tree(
    top_level: list[MenuItemElement], sub_links: SubLinks
) -> list[MenuItemValues]:
    return [
        {
            **_saved_values(item),
            "children": [_saved_values(link) for link in sub_links[item.id]],
        }
        for item in top_level
    ]


def _links_to(item: MenuItemElement, page_id: int) -> bool:
    return (
        item.navigation_type == MenuItemElement.NAVIGATION_TYPES.PAGE
        and item.navigate_to_page_id == page_id
    )


def _check_can_link_to_page(item: MenuItemElement, menu_id: int | None) -> None:
    if item.type == MenuItemElement.TYPES.BUTTON:
        raise ToolInputError(
            f"'{item.name}' is a button, so it can't link to a page. To make it open "
            f"a page, use create_actions with type='open_page', element={menu_id}, "
            f"event='{_click_event(item)}'. {NO_CHANGES}"
        )
    if item.type != MenuItemElement.TYPES.LINK:
        raise ToolInputError(
            f"'{item.name}' is a {item.type}, so it can't link to a page. {NO_CHANGES}"
        )


def _changed(
    item: MenuItemElement, change: MenuItemUpdate | None, menu_id: int | None
) -> MenuItemValues:
    values = _saved_values(item)
    if change is None:
        return values
    if change.name is not None:
        values["name"] = change.name
    if change.page_id is not None:
        _check_can_link_to_page(item, menu_id)
        if not _links_to(item, change.page_id):
            # The parameters belong to the previous page.
            values.update(
                navigation_type=MenuItemElement.NAVIGATION_TYPES.PAGE,
                navigate_to_page_id=change.page_id,
                page_parameters=[],
                query_parameters=[],
            )
    return values


def _insert(
    merged: list[MenuItemValues], new: MenuItemAdd, by_uid: dict[str, MenuItemElement]
) -> None:
    siblings = merged
    if new.parent_uid is not None:
        parent_uid = canonical_uid(new.parent_uid)
        parent = next((item for item in merged if item["uid"] == parent_uid), None)
        if parent is None or parent["type"] != MenuItemElement.TYPES.LINK:
            raise ToolInputError(
                f"{_named(by_uid[parent_uid])} can't have sub-links: only top-level "
                f"links can. {NO_CHANGES}"
            )
        siblings = parent["children"]
    key = name_key(new.name)
    taken = next((item for item in siblings if name_key(item["name"]) == key), None)
    if taken is not None:
        if taken["uid"] not in by_uid:
            raise ToolInputError(
                f"Two new items at that level have the same name, '{taken['name']}' "
                f"and '{new.name}'. Add each item once. {NO_CHANGES}"
            )
        raise ToolInputError(
            f"'{taken['name']}' is already in the menu at that level (uid "
            f"{taken['uid']}). To change it, use update_menu_items. {NO_CHANGES}"
        )
    values = new_menu_link(new.name, new.page_id)
    if new.parent_uid is None:
        values["children"] = []
    if new.before_uid is None:
        siblings.append(values)
        return
    anchor = canonical_uid(new.before_uid)
    position = next(
        (index for index, item in enumerate(siblings) if item["uid"] == anchor), None
    )
    if position is None:
        raise ToolInputError(
            f"{_named(by_uid[anchor])} isn't at the new item's level, so the new item "
            f"can't go before it. {NO_CHANGES}"
        )
    siblings.insert(position, values)


def _click_event(button: MenuItemElement) -> str:
    return f"{button.uid}_click"


def _click_action_counts(
    menu: MenuElement | None, removed: list[MenuItemElement]
) -> dict[str, int]:
    events = [
        _click_event(item)
        for item in removed
        if item.type == MenuItemElement.TYPES.BUTTON
    ]
    if not events:
        return {}
    counts = (
        BuilderWorkflowAction.objects.filter(element=menu, event__in=events)
        .values_list("event")
        .annotate(count=Count("id"))
    )
    return dict(counts)


def _removed_items(
    menu: MenuElement | None, removed: list[MenuItemElement]
) -> list[RemovedMenuItem]:
    click_actions = _click_action_counts(menu, removed)
    items = []
    for item in removed:
        listed = RemovedMenuItem(uid=str(item.uid), name=item.name, type=item.type)
        if item.type == MenuItemElement.TYPES.BUTTON:
            listed["deleted_click_actions"] = click_actions.get(_click_event(item), 0)
        items.append(listed)
    return items
