"""Kuma's builder tools treat each element type through its hooks."""

from typing import Any, NamedTuple
from unittest.mock import MagicMock

import pytest

from baserow.contrib.builder.elements.models import MenuElement
from baserow.contrib.builder.elements.operations import UpdateElementOperationType
from baserow.contrib.builder.pages.models import Page
from baserow.core.exceptions import PermissionDenied
from baserow.test_utils.fixtures import Fixtures
from baserow_enterprise.assistant.tools.builder.assistant_element_types import (
    ButtonAssistantElementType,
    ColumnAssistantElementType,
    FooterAssistantElementType,
    HeaderAssistantElementType,
    LinkAssistantElementType,
    MenuAssistantElementType,
    TableAssistantElementType,
)
from baserow_enterprise.assistant.tools.builder.registries import (
    AssistantElementType,
    PreparedElementUpdate,
    assistant_element_type_registry,
)
from baserow_enterprise.assistant.tools.builder.tools import (
    create_layout_elements,
    update_element,
)
from baserow_enterprise.assistant.tools.builder.types import (
    ElementUpdate,
    LayoutElementCreate,
    MenuItemAdd,
    MenuItemCreate,
)
from baserow_enterprise.assistant.tools.builder.types.element import (
    BUTTON_NAVIGATION_GUIDANCE,
    MENU_ITEM_PROPERTIES,
)
from baserow_enterprise.assistant.tools.shared import ToolInputError
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role

from .utils import make_test_ctx


class SeededPage(NamedTuple):
    ctx: MagicMock
    page: Page


@pytest.fixture
def seeded(data_fixture: Fixtures) -> SeededPage:
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    return SeededPage(make_test_ctx(user, workspace), page)


def test_a_table_gets_the_registered_table_type() -> None:
    table = assistant_element_type_registry.get_for("table")

    assert isinstance(table, TableAssistantElementType)
    assert table is assistant_element_type_registry.get("table")
    assert table.property_aliases == {
        "add_table_columns": "fields",
        "update_table_columns": "fields",
        "reorder_table_columns": "fields",
        "remove_table_columns": "fields",
    }


@pytest.mark.django_db
def test_an_element_type_without_hooks_gets_hooks_that_do_nothing(
    seeded: SeededPage, data_fixture: Fixtures
) -> None:
    heading = data_fixture.create_builder_heading_element(
        page=seeded.page, value="'Title'"
    )
    update = ElementUpdate(element_id=heading.id, value="New title")

    hooks = assistant_element_type_registry.get_for("heading")

    assert hooks.prepare_update(seeded.ctx.deps.user, heading, update) == (
        PreparedElementUpdate(kwargs={}, result={})
    )
    assert hooks.updated_result(heading, update) == {}
    assert hooks.item_details(heading) == {}
    assert hooks.property_aliases == {}
    assert hooks.properties_applied_after_update == frozenset()
    assert hooks.conflicting_properties(update) == []
    assert hooks.after_update(seeded.ctx.deps.user, heading, update) == {}
    heading.refresh_from_db()
    assert heading.value["formula"] == "'Title'"


def test_the_default_guidance_lists_the_supported_properties() -> None:
    hooks = assistant_element_type_registry.get_for("heading")

    assert hooks.unsupported_guidance({"value", "level"}) == (
        "Supported properties include: level, value."
    )


@pytest.mark.parametrize(
    "element_type,registered_type,aliases",
    [
        ("button", ButtonAssistantElementType, {"label": "value"}),
        (
            "link",
            LinkAssistantElementType,
            {"link_variant": "variant", "link_target": "target"},
        ),
        ("column", ColumnAssistantElementType, {"column_alignment": "alignment"}),
        (
            "menu",
            MenuAssistantElementType,
            {
                "menu_orientation": "orientation",
                "menu_alignment": "alignment",
                "add_menu_items": "menu_items",
                "update_menu_items": "menu_items",
                "reorder_menu_items": "menu_items",
                "remove_menu_items": "menu_items",
            },
        ),
    ],
)
def test_an_element_type_with_aliases_gets_its_registered_type(
    element_type: str,
    registered_type: type[AssistantElementType],
    aliases: dict[str, str],
) -> None:
    hooks = assistant_element_type_registry.get_for(element_type)

    assert isinstance(hooks, registered_type)
    assert hooks is assistant_element_type_registry.get(element_type)
    assert hooks.property_aliases == aliases


@pytest.mark.django_db
@pytest.mark.parametrize(
    "element_type,properties,saved",
    [
        (
            "link",
            {"link_variant": "button", "link_target": "blank"},
            {"variant": "button", "target": "blank"},
        ),
        ("column", {"column_alignment": "bottom"}, {"alignment": "bottom"}),
        (
            "menu",
            {"menu_orientation": "vertical", "menu_alignment": "center"},
            {"orientation": "vertical", "alignment": "center"},
        ),
    ],
)
def test_an_aliased_property_is_saved_under_the_kwarg_it_fills(
    seeded: SeededPage,
    data_fixture: Fixtures,
    element_type: str,
    properties: dict[str, str],
    saved: dict[str, str],
) -> None:
    create_element = getattr(data_fixture, f"create_builder_{element_type}_element")
    element = create_element(page=seeded.page)

    result = update_element(
        seeded.ctx,
        page_id=seeded.page.id,
        element=ElementUpdate.model_validate({"element_id": element.id, **properties}),
        thought="Change the element.",
    )

    assert result["updated_fields"] == list(properties)
    element.refresh_from_db()
    assert {name: getattr(element, name) for name in saved} == saved


@pytest.mark.django_db
@pytest.mark.parametrize(
    "properties",
    [{"label": "Buy"}, {"value": "Buy", "label": "Buy"}],
    ids=["label", "same-label-and-value"],
)
def test_a_button_saves_its_label_as_its_value(
    seeded: SeededPage, data_fixture: Fixtures, properties: dict[str, str]
) -> None:
    button = data_fixture.create_builder_button_element(page=seeded.page, value="'Go'")

    result = update_element(
        seeded.ctx,
        page_id=seeded.page.id,
        element=ElementUpdate.model_validate({"element_id": button.id, **properties}),
        thought="Rename the button.",
    )

    assert result["updated_fields"] == list(properties)
    button.refresh_from_db()
    assert button.value["formula"] == "'Buy'"


@pytest.mark.django_db
def test_a_button_label_that_differs_from_its_value_is_refused(
    seeded: SeededPage, data_fixture: Fixtures
) -> None:
    button = data_fixture.create_builder_button_element(page=seeded.page, value="'Go'")

    with pytest.raises(ToolInputError) as raised:
        update_element(
            seeded.ctx,
            page_id=seeded.page.id,
            element=ElementUpdate(element_id=button.id, value="Buy", label="Order"),
            thought="Rename the button.",
        )

    assert str(raised.value) == (
        "Unsupported properties for button: label (conflicts with value). "
        f"No changes were applied. {BUTTON_NAVIGATION_GUIDANCE}"
    )
    button.refresh_from_db()
    assert button.value["formula"] == "'Go'"


@pytest.mark.django_db
def test_a_button_gets_the_navigation_guidance(
    seeded: SeededPage, data_fixture: Fixtures
) -> None:
    button = data_fixture.create_builder_button_element(page=seeded.page, value="'Go'")

    with pytest.raises(ToolInputError) as raised:
        update_element(
            seeded.ctx,
            page_id=seeded.page.id,
            element=ElementUpdate(
                element_id=button.id, navigate_to_page_id=seeded.page.id
            ),
            thought="Make the button open the page.",
        )

    assert str(raised.value) == (
        "Unsupported properties for button: navigate_to_page_id. "
        f"No changes were applied. {BUTTON_NAVIGATION_GUIDANCE}"
    )


@pytest.mark.parametrize(
    "element_type,registered_type",
    [("header", HeaderAssistantElementType), ("footer", FooterAssistantElementType)],
)
def test_a_header_or_footer_applies_its_menu_items_after_the_update(
    element_type: str, registered_type: type[AssistantElementType]
) -> None:
    hooks = assistant_element_type_registry.get_for(element_type)

    assert isinstance(hooks, registered_type)
    assert hooks is assistant_element_type_registry.get(element_type)
    assert hooks.properties_applied_after_update == frozenset(MENU_ITEM_PROPERTIES)


@pytest.mark.django_db
@pytest.mark.parametrize("element_type", ["header", "footer"])
def test_a_header_or_footer_without_a_menu_gets_one_with_its_menu_items(
    seeded: SeededPage, element_type: str
) -> None:
    created = create_layout_elements(
        seeded.ctx,
        page_id=seeded.page.id,
        elements=[LayoutElementCreate(ref="container", type=element_type)],
        thought="Create the shared container.",
    )
    container_id = created["created_elements"][0]["id"]
    assert not MenuElement.objects.filter(page__builder=seeded.page.builder).exists()

    result = update_element(
        seeded.ctx,
        page_id=seeded.page.id,
        element=ElementUpdate(
            element_id=container_id,
            add_menu_items=[MenuItemAdd(name="Home", page_id=seeded.page.id)],
        ),
        thought="Add the navigation.",
    )

    assert result["updated_fields"] == ["add_menu_items"]
    menu = MenuElement.objects.get(page__builder=seeded.page.builder)
    assert menu.parent_element_id == container_id
    assert [
        (item.name, item.navigate_to_page_id) for item in menu.menu_items.all()
    ] == [("Home", seeded.page.id)]


@pytest.mark.django_db
@pytest.mark.parametrize("element_type", ["header", "footer"])
def test_a_header_or_footer_changes_the_items_of_the_menu_inside(
    seeded: SeededPage, data_fixture: Fixtures, element_type: str
) -> None:
    created = create_layout_elements(
        seeded.ctx,
        page_id=seeded.page.id,
        elements=[
            LayoutElementCreate(
                ref="container",
                type=element_type,
                menu_items=[MenuItemCreate(name="Home", page_id=seeded.page.id)],
            )
        ],
        thought="Create the shared navigation.",
    )
    container_id = created["created_elements"][0]["id"]
    menu = MenuElement.objects.get(page__builder=seeded.page.builder)
    assert menu.parent_element_id == container_id
    home = menu.menu_items.get()
    about = data_fixture.create_builder_page(
        builder=seeded.page.builder, name="About", path="/about"
    )

    result = update_element(
        seeded.ctx,
        page_id=seeded.page.id,
        element=ElementUpdate(
            element_id=container_id,
            add_menu_items=[MenuItemAdd(name="About", page_id=about.id)],
            remove_menu_items=[str(home.uid)],
        ),
        thought="Point the navigation to the about page.",
    )

    assert result["updated_fields"] == ["add_menu_items", "remove_menu_items"]
    assert MenuElement.objects.get(page__builder=seeded.page.builder).id == menu.id
    assert [
        (item.name, item.navigate_to_page_id) for item in menu.menu_items.all()
    ] == [("About", about.id)]


@pytest.mark.django_db
def test_a_menu_update_saves_its_menu_items_with_its_other_properties(
    seeded: SeededPage, data_fixture: Fixtures
) -> None:
    menu = data_fixture.create_builder_menu_element(page=seeded.page)

    result = update_element(
        seeded.ctx,
        page_id=seeded.page.id,
        element=ElementUpdate(
            element_id=menu.id,
            menu_orientation="vertical",
            add_menu_items=[MenuItemAdd(name="Home", page_id=seeded.page.id)],
        ),
        thought="Add the navigation.",
    )

    assert result["updated_fields"] == ["menu_orientation", "add_menu_items"]
    menu.refresh_from_db()
    assert menu.orientation == "vertical"
    assert [
        (item.name, item.navigate_to_page_id) for item in menu.menu_items.all()
    ] == [("Home", seeded.page.id)]


@pytest.mark.django_db
def test_a_heading_update_saves_every_property_it_sends(
    seeded: SeededPage, data_fixture: Fixtures
) -> None:
    heading = data_fixture.create_builder_heading_element(
        page=seeded.page, value="'Title'"
    )

    result = update_element(
        seeded.ctx,
        page_id=seeded.page.id,
        element=ElementUpdate(
            element_id=heading.id,
            visibility="logged-in",
            value="New title",
            level=3,
        ),
        thought="Change the heading.",
    )

    assert result["updated_fields"] == ["visibility", "value", "level"]
    heading.refresh_from_db()
    assert (heading.visibility, heading.value["formula"], heading.level) == (
        "logged-in",
        "'New title'",
        3,
    )


@pytest.mark.django_db
def test_the_unsupported_properties_guidance_lists_a_links_aliased_properties(
    seeded: SeededPage, data_fixture: Fixtures
) -> None:
    link = data_fixture.create_builder_link_element(page=seeded.page)

    with pytest.raises(ToolInputError) as raised:
        update_element(
            seeded.ctx,
            page_id=seeded.page.id,
            element=ElementUpdate(element_id=link.id, level=2),
            thought="Change the link.",
        )

    message = str(raised.value)
    assert message.startswith(
        "Unsupported properties for link: level. No changes were applied."
    )
    supported = message.split("Supported properties include: ")[1].rstrip(".")
    assert {"link_variant", "link_target"} <= set(supported.split(", "))


@pytest.mark.django_db
@pytest.mark.parametrize("element_type", ["header", "footer"])
def test_a_header_or_footer_lists_its_menu_item_properties_as_supported(
    seeded: SeededPage, element_type: str
) -> None:
    created = create_layout_elements(
        seeded.ctx,
        page_id=seeded.page.id,
        elements=[LayoutElementCreate(ref="container", type=element_type)],
        thought="Create the shared container.",
    )

    with pytest.raises(ToolInputError) as raised:
        update_element(
            seeded.ctx,
            page_id=seeded.page.id,
            element=ElementUpdate(
                element_id=created["created_elements"][0]["id"], value="x"
            ),
            thought="Change the container.",
        )

    message = str(raised.value)
    assert message.startswith(
        f"Unsupported properties for {element_type}: value. No changes were applied."
    )
    supported = message.split("Supported properties include: ")[1].rstrip(".")
    assert {
        "add_menu_items",
        "update_menu_items",
        "reorder_menu_items",
        "remove_menu_items",
    } <= set(supported.split(", "))


@pytest.mark.django_db
def test_a_heading_update_reports_no_table_keys(
    seeded: SeededPage, data_fixture: Fixtures
) -> None:
    heading = data_fixture.create_builder_heading_element(
        page=seeded.page, value="'Title'"
    )

    result = update_element(
        seeded.ctx,
        page_id=seeded.page.id,
        element=ElementUpdate(element_id=heading.id, value="New title"),
        thought="Rename the heading.",
    )

    assert result == {
        "status": "ok",
        "element_id": heading.id,
        "element_type": "heading",
        "updated_fields": ["value"],
    }
    heading.refresh_from_db()
    assert heading.value["formula"] == "'New title'"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "properties",
    [
        {"value": "New title", "link_target": "blank"},
        {"value": "$formula: a changed heading"},
    ],
    ids=["unsupported-property", "formula"],
)
def test_a_user_who_cannot_update_a_heading_gets_the_permission_error_first(
    seeded: SeededPage,
    data_fixture: Fixtures,
    enterprise_data_fixture: Any,
    enable_enterprise: None,
    synced_roles: None,
    properties: dict[str, str],
) -> None:
    workspace = seeded.ctx.deps.workspace
    heading = data_fixture.create_builder_heading_element(
        page=seeded.page, value="'Title'"
    )
    user = enterprise_data_fixture.create_user()
    enterprise_data_fixture.create_user_workspace(
        user=user, workspace=workspace, permissions="NO_ACCESS"
    )
    role = Role.objects.create(
        name="Read elements without updates", workspace=workspace
    )
    role.operations.set(
        Role.objects.get(uid="BUILDER").operations.exclude(
            name=UpdateElementOperationType.type
        )
    )
    RoleAssignmentHandler._init = False
    RoleAssignmentHandler().assign_role(
        user, workspace, role=role, scope=seeded.page.builder.application_ptr
    )

    with pytest.raises(PermissionDenied):
        update_element(
            make_test_ctx(user, workspace),
            page_id=seeded.page.id,
            element=ElementUpdate.model_validate(
                {"element_id": heading.id, **properties}
            ),
            thought="Change the heading.",
        )

    heading.refresh_from_db()
    assert heading.value["formula"] == "'Title'"
