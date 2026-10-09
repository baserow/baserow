"""Kuma changes a menu's items by uid through update_element."""

import uuid
from typing import Any, Callable, NamedTuple
from unittest.mock import MagicMock

from django.contrib.auth.models import AbstractUser
from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest
from pydantic import ValidationError

from baserow.contrib.builder.elements.actions import (
    CreateElementActionType,
    UpdateElementActionType,
)
from baserow.contrib.builder.elements.models import (
    Element,
    MenuElement,
    MenuItemElement,
)
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.core.action.models import Action
from baserow.test_utils.fixtures import Fixtures
from baserow_enterprise.assistant.tools.builder import helpers
from baserow_enterprise.assistant.tools.builder.tools import (
    list_elements,
    update_element,
)
from baserow_enterprise.assistant.tools.builder.types import ElementUpdate
from baserow_enterprise.assistant.tools.builder.types.menu_items import new_menu_link
from baserow_enterprise.assistant.tools.shared import ToolInputError

from .utils import make_test_ctx

SEEDED_TREE = [("Home", []), ("Products", ["Pricing", "Features"]), ("Help", [])]


class SeededSite(NamedTuple):
    user: AbstractUser
    ctx: MagicMock
    home: Page
    about: Page
    container: Element
    menu: MenuElement
    uids: dict[str, str]


def _seed(data_fixture: Fixtures, container_type: str = "header") -> SeededSite:
    """A header or footer whose menu has a link, a dropdown and a button."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    home = data_fixture.create_builder_page(builder=builder, name="Home", path="/")
    about = data_fixture.create_builder_page(
        builder=builder, name="About", path="/about"
    )
    container = CreateElementActionType.do(
        user,
        element_type_registry.get(container_type),
        builder.shared_page,
        {"share_type": "all"},
    )
    menu = CreateElementActionType.do(
        user,
        element_type_registry.get("menu"),
        builder.shared_page,
        {"reference_element_id": container.id, "position": "child"},
    )
    UpdateElementActionType.do(
        user,
        menu,
        {
            "menu_items": [
                new_menu_link("Home", home.id),
                {
                    **new_menu_link("Products", home.id),
                    "children": [
                        new_menu_link("Pricing", home.id),
                        new_menu_link("Features", home.id),
                    ],
                },
                {
                    "uid": str(uuid.uuid4()),
                    "type": "button",
                    "variant": "button",
                    "name": "Help",
                },
            ]
        },
    )
    menu = MenuElement.objects.get(id=menu.id)
    uids = {item.name: str(item.uid) for item in menu.menu_items.all()}
    data_fixture.create_notification_workflow_action(
        element=menu, event=f"{uids['Help']}_click"
    )
    return SeededSite(
        user, make_test_ctx(user, workspace), home, about, container, menu, uids
    )


@pytest.fixture
def site(data_fixture: Fixtures) -> SeededSite:
    return _seed(data_fixture)


def _update(
    site: SeededSite, element: Element | None = None, **properties: Any
) -> dict[str, Any]:
    return update_element(
        site.ctx,
        page_id=site.home.id,
        element=ElementUpdate.model_validate(
            {"element_id": (element or site.menu).id, **properties}
        ),
        thought="test",
    )


def _tree(menu: MenuElement) -> list[tuple[str, list[str]]]:
    top_level = menu.menu_items.filter(parent_menu_item=None).order_by(
        "menu_item_order"
    )
    return [
        (
            item.name,
            [
                child.name
                for child in item.menu_item_children.order_by("menu_item_order")
            ],
        )
        for item in top_level
    ]


def _help_action_exists(site: SeededSite) -> bool:
    return BuilderWorkflowAction.objects.filter(
        element=site.menu, event=f"{site.uids['Help']}_click"
    ).exists()


def _shared(
    site: SeededSite,
    element_type: str,
    parent: Element | None = None,
    **values: Any,
) -> Element:
    if parent is not None:
        values = {"reference_element_id": parent.id, "position": "child", **values}
    return CreateElementActionType.do(
        site.user,
        element_type_registry.get(element_type),
        site.home.builder.shared_page,
        values,
    )


def _raw_item(item_type: str, name: str, **values: Any) -> dict[str, Any]:
    return {
        "type": item_type,
        "variant": "button" if item_type == "button" else "link",
        "uid": uuid.uuid4(),
        "name": name,
        **values,
    }


def _snapshot(menu: MenuElement) -> dict[str, dict[str, Any]]:
    """Every column of every item but its id, by uid, with the parent's uid."""

    items = list(menu.menu_items.all())
    uids = {item.id: str(item.uid) for item in items}
    return {
        str(item.uid): {
            **{
                field.attname: getattr(item, field.attname)
                for field in MenuItemElement._meta.concrete_fields
                if field.attname not in ("id", "parent_menu_item_id")
            },
            "parent_uid": uids.get(item.parent_menu_item_id),
        }
        for item in items
    }


@pytest.mark.django_db
@pytest.mark.parametrize("target", ["menu", "header", "footer"])
@pytest.mark.parametrize(
    "properties,tree",
    [
        pytest.param(
            lambda s: {"add_menu_items": [{"name": "About", "page_id": s.about.id}]},
            [*SEEDED_TREE, ("About", [])],
            id="add",
        ),
        pytest.param(
            lambda s: {
                "update_menu_items": [{"uid": s.uids["Help"], "name": "Support"}]
            },
            [*SEEDED_TREE[:2], ("Support", [])],
            id="update",
        ),
        pytest.param(
            lambda s: {
                "reorder_menu_items": [
                    s.uids["Help"],
                    s.uids["Home"],
                    s.uids["Products"],
                ]
            },
            [("Help", []), ("Home", []), ("Products", ["Pricing", "Features"])],
            id="reorder",
        ),
        pytest.param(
            lambda s: {"remove_menu_items": [s.uids["Pricing"]]},
            [("Home", []), ("Products", ["Features"]), ("Help", [])],
            id="remove",
        ),
    ],
)
def test_each_menu_item_list_changes_the_menu_and_keeps_the_rest(
    data_fixture: Fixtures,
    target: str,
    properties: Callable[[SeededSite], dict[str, Any]],
    tree: list[tuple[str, list[str]]],
) -> None:
    site = _seed(data_fixture, "footer" if target == "footer" else "header")
    sent = properties(site)

    result = _update(site, site.menu if target == "menu" else site.container, **sent)

    assert result["status"] == "ok"
    assert result["updated_fields"] == list(sent)
    assert _tree(site.menu) == tree
    saved = {str(uid) for uid in site.menu.menu_items.values_list("uid", flat=True)}
    names = {name for top, children in tree for name in (top, *children)}
    assert {site.uids[name] for name in names if name in site.uids} <= saved
    assert site.uids["Help"] in saved
    assert _help_action_exists(site)


@pytest.mark.django_db
def test_items_with_the_same_name_keep_their_own_click_actions(
    data_fixture: Fixtures, site: SeededSite
) -> None:
    buttons = [
        {"uid": str(uuid.uuid4()), "type": "button", "variant": "button", "name": "Go"}
        for _ in range(2)
    ]
    menu = data_fixture.create_builder_menu_element_items(
        page=site.home, menu_items=buttons
    )
    for button in buttons:
        data_fixture.create_notification_workflow_action(
            element=menu, event=f"{button['uid']}_click"
        )

    _update(
        site, menu, update_menu_items=[{"uid": buttons[1]["uid"], "name": "Go now"}]
    )

    saved = menu.menu_items.order_by("menu_item_order")
    assert [(str(item.uid), item.name) for item in saved] == [
        (buttons[0]["uid"], "Go"),
        (buttons[1]["uid"], "Go now"),
    ]
    assert BuilderWorkflowAction.objects.filter(element=menu).count() == 2


@pytest.mark.django_db
def test_renaming_one_item_leaves_every_column_of_every_other_item_as_saved(
    data_fixture: Fixtures, site: SeededSite
) -> None:
    products = data_fixture.create_builder_page(
        builder=site.home.builder,
        name="Products",
        path="/products/:category",
        path_params=[{"name": "category", "type": "text"}],
        query_params=[{"name": "sort", "type": "text"}],
    )
    parameters = {
        "page_parameters": [{"name": "category", "value": "'books'"}],
        "query_parameters": [{"name": "sort", "value": "'price'"}],
    }
    menu = data_fixture.create_builder_menu_element_items(
        page=site.home,
        menu_items=[
            _raw_item(
                "link", "Shop", navigate_to_page=products, target="blank", **parameters
            ),
            _raw_item(
                "link",
                "Docs",
                navigation_type="custom",
                navigate_to_url="'https://docs.example.com'",
                target="blank",
            ),
            _raw_item("button", "Help"),
            _raw_item("spacer", "Gap"),
            _raw_item("link", "Company", navigate_to_page=site.home),
        ],
    )
    company = menu.menu_items.get(name="Company")
    menu.menu_items.add(
        *[
            MenuItemElement.objects.create(
                **values, menu_item_order=order, parent_menu_item=company
            )
            for order, values in enumerate(
                [
                    _raw_item("link", "Team", navigate_to_page=products, **parameters),
                    _raw_item("link", "Jobs", navigate_to_page=site.home),
                ]
            )
        ]
    )
    shop = str(menu.menu_items.get(name="Shop").uid)
    before = _snapshot(menu)

    _update(site, menu, update_menu_items=[{"uid": shop, "name": "Store"}])

    after = _snapshot(menu)
    assert after.pop(shop) == {**before.pop(shop), "name": "Store"}
    assert after == before


@pytest.mark.django_db
@pytest.mark.parametrize("target", ["menu", "header"])
def test_removing_a_button_deletes_its_click_actions_and_reports_them(
    site: SeededSite, target: str
) -> None:
    assert _help_action_exists(site)

    result = _update(
        site,
        site.menu if target == "menu" else site.container,
        remove_menu_items=[site.uids["Help"]],
    )

    assert not _help_action_exists(site)
    assert result["removed_menu_items"] == [
        {
            "uid": site.uids["Help"],
            "name": "Help",
            "type": "button",
            "deleted_click_actions": 1,
        }
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("target", ["menu", "header"])
def test_the_result_lists_the_items_after_the_write_and_the_removed_ones(
    site: SeededSite, target: str
) -> None:
    uids = site.uids

    result = _update(
        site,
        site.menu if target == "menu" else site.container,
        add_menu_items=[
            {"name": "About", "page_id": site.about.id, "parent_uid": uids["Home"]}
        ],
        remove_menu_items=[uids["Products"]],
    )

    about = str(site.menu.menu_items.get(name="About").uid)
    assert result["menu_items"] == [
        {
            "uid": uids["Home"],
            "name": "Home",
            "type": "link",
            "page_id": site.home.id,
            "children": [
                {
                    "uid": about,
                    "name": "About",
                    "type": "link",
                    "page_id": site.about.id,
                }
            ],
        },
        {"uid": uids["Help"], "name": "Help", "type": "button", "page_id": None},
    ]
    assert result["removed_menu_items"] == [
        {"uid": uids["Products"], "name": "Products", "type": "link"},
        {"uid": uids["Pricing"], "name": "Pricing", "type": "link"},
        {"uid": uids["Features"], "name": "Features", "type": "link"},
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("container_type", ["header", "footer"])
def test_a_container_without_a_menu_gets_one_from_its_new_items(
    data_fixture: Fixtures, container_type: str
) -> None:
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    home = data_fixture.create_builder_page(builder=builder, name="Home", path="/")
    container = CreateElementActionType.do(
        user,
        element_type_registry.get(container_type),
        builder.shared_page,
        {"share_type": "all"},
    )
    ctx = make_test_ctx(user, workspace)

    def change(**properties: Any) -> dict[str, Any]:
        return update_element(
            ctx,
            page_id=home.id,
            element=ElementUpdate.model_validate(
                {"element_id": container.id, **properties}
            ),
            thought="test",
        )

    with pytest.raises(ToolInputError, match="The menu has no items yet"):
        change(
            add_menu_items=[
                {"name": "Team", "page_id": home.id, "parent_uid": str(uuid.uuid4())}
            ]
        )
    assert not MenuElement.objects.filter(page__builder=builder).exists()

    result = change(add_menu_items=[{"name": "Home", "page_id": home.id}])

    menu = MenuElement.objects.get(page__builder=builder)
    assert menu.parent_element_id == container.id
    assert _tree(menu) == [("Home", [])]
    assert [item["name"] for item in result["menu_items"]] == ["Home"]


@pytest.mark.django_db
def test_a_refused_menu_change_saves_no_other_property(site: SeededSite) -> None:
    with pytest.raises(ToolInputError, match="not in this menu"):
        _update(
            site, menu_orientation="vertical", remove_menu_items=[str(uuid.uuid4())]
        )

    assert MenuElement.objects.get(id=site.menu.id).orientation == "horizontal"
    assert _tree(site.menu) == SEEDED_TREE


@pytest.mark.django_db
def test_a_refused_header_menu_change_leaves_the_header_unsaved(
    site: SeededSite,
) -> None:
    with pytest.raises(ToolInputError, match="not in this menu"):
        _update(
            site,
            site.container,
            share_type="only",
            remove_menu_items=[str(uuid.uuid4())],
        )

    assert Element.objects.get(id=site.container.id).specific.share_type == "all"
    assert _tree(site.menu) == SEEDED_TREE


@pytest.mark.django_db
def test_the_update_helper_saves_nothing_itself_when_a_menu_change_is_refused(
    site: SeededSite,
) -> None:
    update = ElementUpdate.model_validate(
        {
            "element_id": site.container.id,
            "share_type": "only",
            "remove_menu_items": [str(uuid.uuid4())],
        }
    )

    with pytest.raises(ToolInputError, match="not in this menu"):
        helpers.update_element(site.user, update)

    assert Element.objects.get(id=site.container.id).specific.share_type == "all"
    assert _tree(site.menu) == SEEDED_TREE


@pytest.mark.django_db
@pytest.mark.parametrize("container_type", ["header", "footer"])
def test_a_container_changes_the_menu_nested_inside_it(
    site: SeededSite, container_type: str
) -> None:
    container = _shared(site, container_type, share_type="all")
    column = _shared(site, "column", container)
    nested = _shared(
        site,
        "menu",
        column,
        place_in_container="0",
        menu_items=[new_menu_link("Home", site.home.id)],
    )
    assert (column.parent_element_id, nested.parent_element_id) == (
        container.id,
        column.id,
    )
    menus = MenuElement.objects.filter(page__builder=site.home.builder)
    menus_before = menus.count()

    result = _update(
        site, container, add_menu_items=[{"name": "About", "page_id": site.about.id}]
    )

    assert _tree(nested) == [("Home", []), ("About", [])]
    assert menus.count() == menus_before
    assert [item["name"] for item in result["menu_items"]] == ["Home", "About"]


@pytest.mark.django_db
@pytest.mark.parametrize("container_type", ["header", "footer"])
def test_a_container_with_several_menus_refuses_a_menu_item_change(
    site: SeededSite, container_type: str
) -> None:
    container = _shared(site, container_type, share_type="all")
    menu_ids = [_shared(site, "menu", container).id for _ in range(2)]
    menus_before = MenuElement.objects.count()
    items_before = MenuItemElement.objects.count()

    with pytest.raises(ToolInputError) as raised:
        _update(
            site,
            container,
            add_menu_items=[{"name": "About", "page_id": site.about.id}],
        )

    assert str(raised.value) == (
        f"{container_type.capitalize()} {container.id} holds more than one menu: "
        f"elements {menu_ids}. Change one of them with update_element and that "
        "menu's element_id. No changes were applied."
    )
    assert MenuElement.objects.count() == menus_before
    assert MenuItemElement.objects.count() == items_before


@pytest.mark.django_db
@pytest.mark.parametrize("changed", ["header", "footer"])
def test_a_header_or_footer_changes_only_its_own_menu(
    site: SeededSite, changed: str
) -> None:
    footer = _shared(site, "footer", share_type="all")
    footer_menu = _shared(
        site, "menu", footer, menu_items=[new_menu_link("Terms", site.home.id)]
    )
    container = site.container if changed == "header" else footer
    added = [{"name": "About", "page_id": site.about.id}]

    _update(site, container, add_menu_items=added)

    if changed == "header":
        assert _tree(site.menu) == [*SEEDED_TREE, ("About", [])]
        assert _tree(footer_menu) == [("Terms", [])]
    else:
        assert _tree(footer_menu) == [("Terms", []), ("About", [])]
        assert _tree(site.menu) == SEEDED_TREE


@pytest.mark.django_db
def test_all_menu_item_lists_and_other_properties_are_saved_as_one_action(
    site: SeededSite,
) -> None:
    uids = site.uids
    before = Action.objects.filter(type=UpdateElementActionType.type).count()

    _update(
        site,
        menu_orientation="vertical",
        add_menu_items=[{"name": "About", "page_id": site.about.id}],
        update_menu_items=[{"uid": uids["Help"], "name": "Support"}],
        reorder_menu_items=[uids["Help"], uids["Home"], uids["Products"]],
        remove_menu_items=[uids["Pricing"]],
    )

    assert _tree(site.menu) == [
        ("Support", []),
        ("Home", []),
        ("Products", ["Features"]),
        ("About", []),
    ]
    assert MenuElement.objects.get(id=site.menu.id).orientation == "vertical"
    after = Action.objects.filter(type=UpdateElementActionType.type).count()
    assert after == before + 1


@pytest.mark.django_db
def test_empty_menu_item_lists_count_as_not_set(site: SeededSite) -> None:
    result = _update(
        site,
        menu_alignment="center",
        add_menu_items=[],
        update_menu_items=[],
        reorder_menu_items=[],
        remove_menu_items=[],
    )

    assert result["updated_fields"] == ["menu_alignment"]
    assert "menu_items" not in result
    assert _tree(site.menu) == SEEDED_TREE


def test_updates_no_longer_take_the_whole_menu_items_list() -> None:
    with pytest.raises(ValidationError):
        ElementUpdate.model_validate({"element_id": 1, "menu_items": []})


@pytest.mark.django_db
def test_query_count_does_not_grow_with_the_items(
    data_fixture: Fixtures, site: SeededSite
) -> None:
    def count_queries(size: int) -> int:
        menu = data_fixture.create_builder_menu_element_items(
            page=site.home,
            menu_items=[
                new_menu_link(f"Link {index}", site.home.id) for index in range(size)
            ],
        )
        uid = str(menu.menu_items.first().uid)
        with CaptureQueriesContext(connection) as queries:
            _update(site, menu, update_menu_items=[{"uid": uid, "name": "Renamed"}])
        return len(queries)

    count_queries(1)
    assert count_queries(5) == count_queries(10)


@pytest.mark.django_db
def test_list_elements_shows_menu_items_with_uids_and_sub_links(
    site: SeededSite,
) -> None:
    uids = site.uids

    result = list_elements(site.ctx, page_id=site.home.id, thought="test")

    def listed(name: str, item_type: str, page: Page | None) -> dict[str, Any]:
        return {
            "uid": uids[name],
            "name": name,
            "type": item_type,
            "page_id": page and page.id,
        }

    menu = next(item for item in result["elements"] if item["type"] == "menu")
    assert menu["menu_items"] == [
        listed("Home", "link", site.home),
        {
            **listed("Products", "link", site.home),
            "children": [
                listed("Pricing", "link", site.home),
                listed("Features", "link", site.home),
            ],
        },
        listed("Help", "button", None),
    ]
    assert all(
        "menu_items" not in element
        for element in result["elements"]
        if element["type"] != "menu"
    )


@pytest.mark.django_db
def test_list_elements_shows_the_url_of_a_custom_link_but_no_other_item(
    data_fixture: Fixtures, site: SeededSite
) -> None:
    menu = data_fixture.create_builder_menu_element_items(
        page=site.home,
        menu_items=[
            _raw_item("link", "Shop", navigate_to_page=site.about),
            _raw_item(
                "link",
                "Docs",
                navigation_type="custom",
                navigate_to_url="'https://docs.example.com'",
            ),
            _raw_item("separator", "Line"),
        ],
    )
    uids = {item.name: str(item.uid) for item in menu.menu_items.all()}

    result = list_elements(site.ctx, page_id=site.home.id, thought="test")

    listed = next(element for element in result["elements"] if element["id"] == menu.id)
    assert listed["menu_items"] == [
        {"uid": uids["Shop"], "name": "Shop", "type": "link", "page_id": site.about.id},
        {
            "uid": uids["Docs"],
            "name": "Docs",
            "type": "link",
            "page_id": None,
            "url": "'https://docs.example.com'",
        },
        {"uid": uids["Line"], "name": "Line", "type": "separator", "page_id": None},
    ]


@pytest.mark.django_db
def test_finding_the_menu_of_a_header_locks_it(
    site: SeededSite,
) -> None:
    with CaptureQueriesContext(connection) as queries:
        menu = helpers.child_menu(site.container)

    assert menu is not None and menu.id == site.menu.id
    assert any("FOR UPDATE" in query["sql"] for query in queries)
