"""Kuma's menu item changes merge into the full item list core saves."""

import uuid
from typing import Any, Callable, NamedTuple

from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest
from pydantic import ValidationError

from baserow.contrib.builder.elements.models import MenuElement, MenuItemElement
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.test_utils.fixtures import Fixtures
from baserow_enterprise.assistant.tools.builder.menu_item_changes import (
    MenuItemsChange,
    linkable_page_ids,
    merge_menu_items,
)
from baserow_enterprise.assistant.tools.builder.types.menu_items import (
    MenuItemAdd,
    MenuItemUpdate,
)
from baserow_enterprise.assistant.tools.shared import ToolInputError

UNKNOWN_UID = "00000000-0000-0000-0000-000000000000"
STRUCTURE_FIELDS = frozenset({"id", "menu_item_order", "parent_menu_item_id"})
SEEDED_TREE = [
    ("Home", []),
    ("Products", ["Pricing", "Features"]),
    ("Docs", []),
    ("Divider", []),
    ("Help", []),
]


class SeededMenu(NamedTuple):
    menu: MenuElement
    pages: dict[str, Page]
    uids: dict[str, str]


def _link(name: str, page: Page | None = None, **values: Any) -> dict[str, Any]:
    return {
        "type": "link",
        "variant": "link",
        "uid": uuid.uuid4(),
        "name": name,
        "navigate_to_page": page,
        **values,
    }


def _item(item_type: str, name: str, **values: Any) -> dict[str, Any]:
    return {
        "type": item_type,
        "variant": "link",
        "uid": uuid.uuid4(),
        "name": name,
        **values,
    }


@pytest.fixture
def seeded(data_fixture: Fixtures) -> SeededMenu:
    """A menu with a link, a dropdown, a custom link, a separator and a button."""

    builder = data_fixture.create_builder_application()
    pages = {
        name: data_fixture.create_builder_page(builder=builder, name=name, path=path)
        for name, path in (("Home", "/"), ("About", "/about"), ("Contact", "/contact"))
    }
    pages["Products"] = data_fixture.create_builder_page(
        builder=builder,
        name="Products",
        path="/products/:category",
        path_params=[{"name": "category", "type": "text"}],
        query_params=[{"name": "sort", "type": "text"}],
    )
    menu = data_fixture.create_builder_menu_element_items(
        page=pages["Home"],
        menu_items=[
            _link("Home", pages["Home"]),
            _link(
                "Products",
                pages["Products"],
                target="blank",
                page_parameters=[{"name": "category", "value": "'books'"}],
                query_parameters=[{"name": "sort", "value": "'price'"}],
            ),
            _link(
                "Docs",
                navigation_type="custom",
                navigate_to_url="'https://docs.example.com'",
            ),
            _item("separator", "Divider"),
            _item("button", "Help", variant="button"),
        ],
    )
    products = menu.menu_items.get(name="Products")
    menu.menu_items.add(
        *[
            MenuItemElement.objects.create(
                **values, menu_item_order=order, parent_menu_item=products
            )
            for order, values in enumerate(
                [_link("Pricing", pages["Home"]), _link("Features", pages["Home"])]
            )
        ]
    )
    uids = {item.name: str(item.uid) for item in menu.menu_items.all()}
    data_fixture.create_notification_workflow_action(
        element=menu, event=f"{uids['Help']}_click"
    )
    return SeededMenu(menu, pages, uids)


def _linkable(seeded: SeededMenu) -> frozenset[int]:
    return linkable_page_ids(seeded.pages["Home"].builder_id)


def _merge(
    seeded: SeededMenu,
    add: list[dict[str, Any]] | None = None,
    update: list[dict[str, Any]] | None = None,
    reorder: list[str] | None = None,
    remove: list[str] | None = None,
) -> MenuItemsChange:
    return merge_menu_items(
        MenuElement.objects.get(id=seeded.menu.id),
        page_ids=_linkable(seeded),
        add=[MenuItemAdd.model_validate(entry) for entry in add or []],
        update=[MenuItemUpdate.model_validate(entry) for entry in update or []],
        reorder=reorder,
        remove=remove or [],
    )


def _menu_of_buttons(
    data_fixture: Fixtures, seeded: SeededMenu, click_actions: tuple[int, ...]
) -> SeededMenu:
    menu = data_fixture.create_builder_menu_element_items(
        page=seeded.pages["About"],
        menu_items=[
            _item("button", f"Button {number}", variant="button")
            for number in range(len(click_actions))
        ],
    )
    uids = {item.name: str(item.uid) for item in menu.menu_items.all()}
    for uid, count in zip(uids.values(), click_actions):
        for _ in range(count):
            data_fixture.create_notification_workflow_action(
                element=menu, event=f"{uid}_click"
            )
    return SeededMenu(menu, seeded.pages, uids)


def _tree(change: MenuItemsChange) -> list[tuple[str, list[str]]]:
    return [
        (item["name"], [child["name"] for child in item["children"]])
        for item in change.menu_items
    ]


def _values(change: MenuItemsChange) -> dict[str, dict[str, Any]]:
    flat = {}
    for item in change.menu_items:
        flat[item["uid"]] = {
            key: value for key, value in item.items() if key != "children"
        }
        for child in item["children"]:
            flat[child["uid"]] = child
    return flat


def _saved(seeded: SeededMenu, name: str) -> dict[str, Any]:
    item = MenuItemElement.objects.get(uid=seeded.uids[name])
    return {
        field.attname: (
            str(item.uid) if field.attname == "uid" else getattr(item, field.attname)
        )
        for field in MenuItemElement._meta.concrete_fields
        if field.attname not in STRUCTURE_FIELDS
    }


def _refused(seeded: SeededMenu, message: str, **changes: Any) -> None:
    with pytest.raises(ToolInputError) as raised:
        _merge(seeded, **changes)
    assert message in str(raised.value)
    assert str(raised.value).endswith("No changes were applied.")


@pytest.mark.django_db
def test_items_the_changes_do_not_name_are_resent_exactly_as_saved(
    seeded: SeededMenu,
) -> None:
    change = _merge(seeded, update=[{"uid": seeded.uids["Home"], "name": "Start"}])

    values = _values(change)
    for name in ("Products", "Pricing", "Features", "Docs", "Divider", "Help"):
        assert values[seeded.uids[name]] == _saved(seeded, name)
    assert values[seeded.uids["Home"]] == {**_saved(seeded, "Home"), "name": "Start"}
    assert _tree(change) == [("Start", []), *SEEDED_TREE[1:]]
    assert change.removed == []


@pytest.mark.django_db
def test_a_new_link_goes_last_at_its_level(seeded: SeededMenu) -> None:
    change = _merge(
        seeded,
        add=[
            {"name": "Contact", "page_id": seeded.pages["Contact"].id},
            {
                "name": "Changelog",
                "page_id": seeded.pages["About"].id,
                "parent_uid": seeded.uids["Products"],
            },
        ],
    )

    assert _tree(change) == [
        ("Home", []),
        ("Products", ["Pricing", "Features", "Changelog"]),
        ("Docs", []),
        ("Divider", []),
        ("Help", []),
        ("Contact", []),
    ]
    contact = change.menu_items[-1]
    assert contact == {
        "uid": contact["uid"],
        "type": "link",
        "variant": "link",
        "name": "Contact",
        "navigation_type": "page",
        "navigate_to_page_id": seeded.pages["Contact"].id,
        "target": "self",
        "children": [],
    }
    assert contact["uid"] not in seeded.uids.values()


@pytest.mark.django_db
def test_new_links_go_before_their_anchor_in_the_order_sent(
    seeded: SeededMenu,
) -> None:
    uids = seeded.uids

    change = _merge(
        seeded,
        add=[
            {
                "name": "Contact",
                "page_id": seeded.pages["Contact"].id,
                "before_uid": uids["Divider"],
            },
            {
                "name": "About",
                "page_id": seeded.pages["About"].id,
                "before_uid": uids["Divider"],
            },
            {
                "name": "Changelog",
                "page_id": seeded.pages["About"].id,
                "parent_uid": uids["Products"],
                "before_uid": uids["Features"],
            },
        ],
    )

    assert _tree(change) == [
        ("Home", []),
        ("Products", ["Pricing", "Changelog", "Features"]),
        ("Docs", []),
        ("Contact", []),
        ("About", []),
        ("Divider", []),
        ("Help", []),
    ]


@pytest.mark.django_db
def test_pointing_a_link_to_another_page_clears_its_parameters(
    seeded: SeededMenu,
) -> None:
    products = seeded.uids["Products"]

    change = _merge(
        seeded, update=[{"uid": products, "page_id": seeded.pages["About"].id}]
    )

    assert _values(change)[products] == {
        **_saved(seeded, "Products"),
        "navigate_to_page_id": seeded.pages["About"].id,
        "page_parameters": [],
        "query_parameters": [],
    }


@pytest.mark.django_db
def test_resending_a_links_page_keeps_its_parameters(seeded: SeededMenu) -> None:
    products = seeded.uids["Products"]

    change = _merge(
        seeded,
        update=[
            {"uid": products, "name": "Shop", "page_id": seeded.pages["Products"].id}
        ],
    )

    assert _values(change)[products] == {**_saved(seeded, "Products"), "name": "Shop"}


@pytest.mark.django_db
def test_pointing_a_custom_link_to_a_page_makes_it_a_page_link(
    seeded: SeededMenu,
) -> None:
    docs = seeded.uids["Docs"]

    change = _merge(seeded, update=[{"uid": docs, "page_id": seeded.pages["About"].id}])

    assert _values(change)[docs] == {
        **_saved(seeded, "Docs"),
        "navigation_type": "page",
        "navigate_to_page_id": seeded.pages["About"].id,
        "page_parameters": [],
        "query_parameters": [],
    }


@pytest.mark.django_db
def test_a_sub_link_can_be_renamed(seeded: SeededMenu) -> None:
    change = _merge(seeded, update=[{"uid": seeded.uids["Pricing"], "name": "Plans"}])

    assert _tree(change)[1] == ("Products", ["Plans", "Features"])


@pytest.mark.django_db
def test_reordering_moves_top_level_items_with_their_sub_links(
    seeded: SeededMenu,
) -> None:
    order = ("Help", "Products", "Home", "Docs", "Divider")

    change = _merge(seeded, reorder=[seeded.uids[name] for name in order])

    assert _tree(change) == [
        ("Help", []),
        ("Products", ["Pricing", "Features"]),
        ("Home", []),
        ("Docs", []),
        ("Divider", []),
    ]


@pytest.mark.django_db
def test_removing_a_sub_link(seeded: SeededMenu) -> None:
    change = _merge(seeded, remove=[seeded.uids["Pricing"]])

    assert _tree(change)[1] == ("Products", ["Features"])
    assert change.removed == [
        {"uid": seeded.uids["Pricing"], "name": "Pricing", "type": "link"}
    ]


@pytest.mark.django_db
def test_removing_a_dropdown_removes_its_sub_links(seeded: SeededMenu) -> None:
    uids = seeded.uids

    change = _merge(seeded, remove=[uids["Products"]])

    assert _tree(change) == [("Home", []), ("Docs", []), ("Divider", []), ("Help", [])]
    assert change.removed == [
        {"uid": uids["Products"], "name": "Products", "type": "link"},
        {"uid": uids["Pricing"], "name": "Pricing", "type": "link"},
        {"uid": uids["Features"], "name": "Features", "type": "link"},
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("actions", [1, 0])
def test_a_removed_button_reports_its_deleted_click_actions(
    seeded: SeededMenu, actions: int
) -> None:
    if not actions:
        BuilderWorkflowAction.objects.filter(element=seeded.menu).delete()

    change = _merge(seeded, remove=[seeded.uids["Help"]])

    assert change.removed == [
        {
            "uid": seeded.uids["Help"],
            "name": "Help",
            "type": "button",
            "deleted_click_actions": actions,
        }
    ]


@pytest.mark.django_db
def test_removed_buttons_are_counted_in_one_query(
    seeded: SeededMenu, data_fixture: Fixtures
) -> None:
    queries = {}
    for removing in (1, 3):
        buttons = _menu_of_buttons(data_fixture, seeded, click_actions=(1, 1, 1))
        with CaptureQueriesContext(connection) as captured:
            change = _merge(buttons, remove=list(buttons.uids.values())[:removing])
        queries[removing] = len(captured)
        counts = [item["deleted_click_actions"] for item in change.removed]
        assert counts == [1] * removing

    assert queries[1] == queries[3]


@pytest.mark.django_db
def test_each_removed_button_reports_its_own_click_actions(
    seeded: SeededMenu, data_fixture: Fixtures
) -> None:
    buttons = _menu_of_buttons(data_fixture, seeded, click_actions=(2, 0, 1))

    change = _merge(buttons, remove=list(buttons.uids.values()))

    counts = [item["deleted_click_actions"] for item in change.removed]
    assert counts == [2, 0, 1]


@pytest.mark.django_db
def test_a_name_freed_in_the_same_call_can_be_reused(seeded: SeededMenu) -> None:
    change = _merge(
        seeded,
        remove=[seeded.uids["Help"]],
        add=[{"name": "Help", "page_id": seeded.pages["About"].id}],
    )

    assert _tree(change)[-1] == ("Help", [])
    assert change.menu_items[-1]["type"] == "link"
    assert change.removed[0]["deleted_click_actions"] == 1


@pytest.mark.django_db
def test_changes_apply_as_removals_updates_reorder_then_additions(
    seeded: SeededMenu,
) -> None:
    uids = seeded.uids

    change = _merge(
        seeded,
        remove=[uids["Docs"]],
        update=[{"uid": uids["Help"], "name": "Support"}],
        reorder=[uids[name] for name in ("Help", "Home", "Products", "Divider")],
        add=[
            {
                "name": "Contact",
                "page_id": seeded.pages["Contact"].id,
                "before_uid": uids["Home"],
            }
        ],
    )

    assert _tree(change) == [
        ("Support", []),
        ("Contact", []),
        ("Home", []),
        ("Products", ["Pricing", "Features"]),
        ("Divider", []),
    ]


@pytest.mark.django_db
def test_uids_match_whatever_their_case_and_surrounding_spaces(
    seeded: SeededMenu,
) -> None:
    sent = f" {seeded.uids['Home'].upper()} "

    change = _merge(seeded, update=[{"uid": sent, "name": "Start"}])

    assert _tree(change)[0] == ("Start", [])


@pytest.mark.django_db
def test_a_missing_menu_takes_only_new_items(seeded: SeededMenu) -> None:
    change = merge_menu_items(
        None,
        page_ids=_linkable(seeded),
        add=[MenuItemAdd(name="Home", page_id=seeded.pages["Home"].id)],
        update=[],
        reorder=None,
        remove=[],
    )

    assert _tree(change) == [("Home", [])]
    assert change.removed == []


@pytest.mark.django_db
def test_a_uid_is_refused_when_there_is_no_menu_yet(seeded: SeededMenu) -> None:
    with pytest.raises(ToolInputError, match="The menu has no items yet"):
        merge_menu_items(
            None,
            page_ids=_linkable(seeded),
            add=[],
            update=[],
            reorder=None,
            remove=[seeded.uids["Home"]],
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "changes",
    [
        {"update": [{"uid": UNKNOWN_UID, "name": "X"}]},
        {"remove": [UNKNOWN_UID]},
        {"reorder": [UNKNOWN_UID]},
        {"add": [{"name": "X", "page_id": 1, "parent_uid": UNKNOWN_UID}]},
        {"add": [{"name": "X", "page_id": 1, "before_uid": UNKNOWN_UID}]},
    ],
    ids=["update", "remove", "reorder", "parent_uid", "before_uid"],
)
def test_an_unknown_uid_is_refused_with_the_items_to_use(
    seeded: SeededMenu, changes: dict[str, Any]
) -> None:
    _refused(
        seeded,
        f"Menu items ['{UNKNOWN_UID}'] are not in this menu. Its items are: "
        f"'Home' (uid {seeded.uids['Home']}), 'Products' (uid "
        f"{seeded.uids['Products']}), 'Pricing' (uid {seeded.uids['Pricing']})",
        **changes,
    )


@pytest.mark.django_db
def test_an_item_changed_twice_is_refused(seeded: SeededMenu) -> None:
    home = seeded.uids["Home"]

    _refused(
        seeded,
        f"These menu items are changed more than once: 'Home' (uid {home})",
        update=[
            {"uid": home, "name": "Start"},
            {"uid": home, "page_id": seeded.pages["About"].id},
        ],
    )


@pytest.mark.django_db
@pytest.mark.parametrize("removed", ["Pricing", "Products"], ids=["itself", "dropdown"])
def test_an_item_changed_and_removed_is_refused(
    seeded: SeededMenu, removed: str
) -> None:
    pricing = seeded.uids["Pricing"]

    _refused(
        seeded,
        f"These menu items are changed and removed: 'Pricing' (uid {pricing})",
        update=[{"uid": pricing, "name": "Plans"}],
        remove=[seeded.uids[removed]],
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "order,removed,problem,named",
    [
        (("Home", "Products", "Docs", "Divider"), [], "Missing", "Help"),
        (
            ("Home", "Products", "Docs", "Divider", "Help", "Help"),
            [],
            "Listed more than once",
            "Help",
        ),
        (
            ("Home", "Products", "Docs", "Divider", "Help"),
            ["Help"],
            "Removed in this call",
            "Help",
        ),
        (
            ("Home", "Products", "Docs", "Divider", "Help", "Pricing"),
            [],
            "Sub-links, which can't be reordered",
            "Pricing",
        ),
    ],
    ids=["missing", "repeated", "removed", "sub-link"],
)
def test_a_reorder_must_list_every_top_level_item_that_stays_once(
    seeded: SeededMenu,
    order: tuple[str, ...],
    removed: list[str],
    problem: str,
    named: str,
) -> None:
    _refused(
        seeded,
        f"{problem}: '{named}' (uid {seeded.uids[named]})",
        reorder=[seeded.uids[name] for name in order],
        remove=[seeded.uids[name] for name in removed],
    )


@pytest.mark.django_db
@pytest.mark.parametrize("anchor", ["parent_uid", "before_uid"])
def test_a_new_item_cannot_go_under_or_before_a_removed_item(
    seeded: SeededMenu, anchor: str
) -> None:
    products = seeded.uids["Products"]

    _refused(
        seeded,
        "These menu items are removed in this call, so new items can't go under "
        f"or before them: 'Products' (uid {products})",
        add=[{"name": "X", "page_id": seeded.pages["About"].id, anchor: products}],
        remove=[products],
    )


@pytest.mark.django_db
@pytest.mark.parametrize("parent", ["Pricing", "Help", "Divider"])
def test_only_a_top_level_link_can_take_sub_links(
    seeded: SeededMenu, parent: str
) -> None:
    _refused(
        seeded,
        f"'{parent}' (uid {seeded.uids[parent]}) can't have sub-links: only "
        "top-level links can.",
        add=[
            {
                "name": "X",
                "page_id": seeded.pages["About"].id,
                "parent_uid": seeded.uids[parent],
            }
        ],
    )


@pytest.mark.django_db
def test_parent_and_before_uids_match_whatever_their_case_and_spaces(
    seeded: SeededMenu,
) -> None:
    uids = seeded.uids

    change = _merge(
        seeded,
        add=[
            {
                "name": "Changelog",
                "page_id": seeded.pages["About"].id,
                "parent_uid": f" {uids['Products'].upper()} ",
                "before_uid": f" {uids['Features'].upper()} ",
            }
        ],
    )

    assert _tree(change)[1] == ("Products", ["Pricing", "Changelog", "Features"])


@pytest.mark.django_db
def test_before_uid_must_be_at_the_new_items_level(seeded: SeededMenu) -> None:
    pricing = seeded.uids["Pricing"]

    _refused(
        seeded,
        f"'Pricing' (uid {pricing}) isn't at the new item's level, so the new item "
        "can't go before it.",
        add=[{"name": "X", "page_id": seeded.pages["About"].id, "before_uid": pricing}],
    )


@pytest.mark.django_db
def test_a_new_sub_link_cannot_go_before_a_top_level_item(
    seeded: SeededMenu,
) -> None:
    home = seeded.uids["Home"]

    _refused(
        seeded,
        f"'Home' (uid {home}) isn't at the new item's level, so the new item can't go "
        "before it.",
        add=[
            {
                "name": "X",
                "page_id": seeded.pages["About"].id,
                "parent_uid": seeded.uids["Products"],
                "before_uid": home,
            }
        ],
    )


@pytest.mark.django_db
def test_a_new_item_named_like_a_sibling_is_refused(seeded: SeededMenu) -> None:
    _refused(
        seeded,
        f"'Home' is already in the menu at that level (uid {seeded.uids['Home']}). "
        "To change it, use update_menu_items.",
        add=[{"name": " home ", "page_id": seeded.pages["About"].id}],
    )


@pytest.mark.django_db
def test_a_new_sub_link_named_like_a_sibling_is_refused(seeded: SeededMenu) -> None:
    _refused(
        seeded,
        f"'Pricing' is already in the menu at that level (uid "
        f"{seeded.uids['Pricing']}).",
        add=[
            {
                "name": "pricing",
                "page_id": seeded.pages["About"].id,
                "parent_uid": seeded.uids["Products"],
            }
        ],
    )


@pytest.mark.django_db
def test_a_name_is_only_taken_at_its_own_level(seeded: SeededMenu) -> None:
    change = _merge(
        seeded, add=[{"name": "Pricing", "page_id": seeded.pages["About"].id}]
    )

    assert _tree(change)[-1] == ("Pricing", [])


@pytest.mark.django_db
def test_two_new_items_with_the_same_name_are_refused(seeded: SeededMenu) -> None:
    about = seeded.pages["About"].id

    _refused(
        seeded,
        "Two new items at that level have the same name, 'Blog' and 'blog'.",
        add=[{"name": "Blog", "page_id": about}, {"name": "blog", "page_id": about}],
    )


@pytest.mark.django_db
def test_a_page_on_a_button_points_to_click_actions(seeded: SeededMenu) -> None:
    help_uid = seeded.uids["Help"]

    _refused(
        seeded,
        "'Help' is a button, so it can't link to a page. To make it open a page, use "
        f"create_actions with type='open_page', element={seeded.menu.id}, "
        f"event='{help_uid}_click'.",
        update=[{"uid": help_uid, "page_id": seeded.pages["About"].id}],
    )


@pytest.mark.django_db
def test_a_button_refuses_a_page_whatever_page_it_stores(
    seeded: SeededMenu,
) -> None:
    help_uid = seeded.uids["Help"]
    about = seeded.pages["About"]
    MenuItemElement.objects.filter(uid=help_uid).update(navigate_to_page_id=about.id)

    _refused(
        seeded,
        "'Help' is a button, so it can't link to a page.",
        update=[{"uid": help_uid, "page_id": about.id}],
    )


@pytest.mark.django_db
@pytest.mark.parametrize("sent_in", ["add", "update"])
@pytest.mark.parametrize(
    "page_id_of",
    [
        lambda seeded, data_fixture: data_fixture.create_builder_page().id,
        lambda seeded, data_fixture: seeded.pages["Home"].builder.shared_page.id,
        lambda seeded, data_fixture: 99999999,
    ],
    ids=["another application", "shared page", "missing"],
)
def test_a_page_outside_the_application_is_refused(
    seeded: SeededMenu,
    data_fixture: Fixtures,
    page_id_of: Callable[[SeededMenu, Fixtures], int],
    sent_in: str,
) -> None:
    page_id = page_id_of(seeded, data_fixture)
    changes = {
        "add": {"add": [{"name": "X", "page_id": page_id}]},
        "update": {"update": [{"uid": seeded.uids["Home"], "page_id": page_id}]},
    }

    _refused(
        seeded,
        f"Pages [{page_id}] aren't pages of this application.",
        **changes[sent_in],
    )


@pytest.mark.django_db
def test_unknown_pages_are_listed_once_in_the_order_sent(seeded: SeededMenu) -> None:
    _refused(
        seeded,
        "Pages [99999998, 99999999, 99999997] aren't pages of this application.",
        add=[
            {"name": "A", "page_id": 99999998},
            {"name": "B", "page_id": 99999999},
            {"name": "C", "page_id": 99999998},
        ],
        update=[{"uid": seeded.uids["Home"], "page_id": 99999997}],
    )


@pytest.mark.django_db
def test_a_page_on_a_separator_is_refused(seeded: SeededMenu) -> None:
    _refused(
        seeded,
        "'Divider' is a separator, so it can't link to a page.",
        update=[{"uid": seeded.uids["Divider"], "page_id": seeded.pages["About"].id}],
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "changes",
    [
        lambda s: {"update": [{"uid": s.uids["Home"], "name": "Home"}]},
        lambda s: {
            "update": [{"uid": s.uids["Products"], "page_id": s.pages["Products"].id}]
        },
        lambda s: {
            "reorder": [
                s.uids[name] for name in ("Home", "Products", "Docs", "Divider", "Help")
            ]
        },
    ],
    ids=["same name", "same page", "same order"],
)
def test_a_call_that_changes_nothing_is_refused(
    seeded: SeededMenu, changes: Callable[[SeededMenu], dict[str, Any]]
) -> None:
    _refused(seeded, "No menu item would change", **changes(seeded))


@pytest.mark.parametrize(
    "model,entry",
    [
        (MenuItemAdd, {"name": "  ", "page_id": 1}),
        (MenuItemUpdate, {"uid": "m1", "name": " "}),
    ],
    ids=["add", "update"],
)
def test_a_blank_name_is_refused(
    model: type[MenuItemAdd] | type[MenuItemUpdate], entry: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError, match="A menu item name can't be blank."):
        model.model_validate(entry)


def test_an_item_update_must_change_something() -> None:
    with pytest.raises(
        ValidationError, match="Menu item m1 needs a new name or page_id."
    ):
        MenuItemUpdate.model_validate({"uid": "m1"})
