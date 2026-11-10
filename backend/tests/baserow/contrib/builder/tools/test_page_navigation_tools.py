"""
A page's parameters and the links and click actions that open it: update_page lists
the ones a change breaks, and update_element can give a link new parameters.
"""

import pytest

from baserow.contrib.builder.elements.models import LinkElement, MenuItemElement
from baserow.contrib.builder.tools import elements, pages
from baserow.contrib.builder.tools.types import ElementEdits, PageChanges
from baserow.core.tools.errors import ToolInputError


@pytest.fixture
def product_page(data_fixture, builder_ctx):
    page = data_fixture.create_builder_page(
        builder=builder_ctx["builder"],
        name="Product",
        path="/products/:id",
        path_params=[{"name": "id", "type": "numeric"}],
    )
    link = data_fixture.create_builder_link_element(
        page=builder_ctx["page"],
        navigation_type="page",
        navigate_to_page_id=page.id,
        page_parameters=[{"name": "id", "value": "'1'"}],
    )
    action = data_fixture.create_open_page_workflow_action(
        page=builder_ctx["page"],
        element=builder_ctx["button"],
        event="click",
        navigation_type="page",
        navigate_to_page_id=page.id,
        page_parameters=[{"name": "id", "value": "'1'"}],
    )
    return page, link, action


def _stored(link):
    saved = LinkElement.objects.get(id=link.id)
    return [(p["name"], p["value"]["formula"]) for p in saved.page_parameters]


@pytest.mark.django_db
def test_update_page_lists_the_navigations_its_new_parameters_break(
    builder_ctx, product_page
):
    page, link, action = product_page

    result = pages.update_page(
        builder_ctx["ctx"], page.id, PageChanges(path="/products/:slug")
    )

    to_fix = result["navigations_to_fix"]
    assert {(n["type"], n["element_id"]) for n in to_fix} == {
        ("link", link.id),
        ("open_page action", builder_ctx["button"].id),
    }
    assert all("slug" in n["fix"] for n in to_fix)


@pytest.mark.django_db
def test_update_page_lists_nothing_when_the_parameters_stay(builder_ctx, product_page):
    page, _link, _action = product_page

    result = pages.update_page(
        builder_ctx["ctx"], page.id, PageChanges(path="/items/:id")
    )

    assert "navigations_to_fix" not in result


@pytest.mark.django_db
def test_update_element_gives_a_link_the_new_parameters(builder_ctx, product_page):
    page, link, _action = product_page
    pages.update_page(builder_ctx["ctx"], page.id, PageChanges(path="/products/:slug"))

    result = elements.update_element(
        builder_ctx["ctx"],
        link.id,
        ElementEdits(link_page_parameters=[{"name": "slug", "value": "shoes"}]),
    )

    assert "formula_errors" not in result
    assert _stored(link) == [("slug", "'shoes'")]
    after = pages.update_page(builder_ctx["ctx"], page.id, PageChanges(name="Item"))
    assert "navigations_to_fix" not in after


@pytest.mark.django_db
def test_update_element_stores_a_link_parameter_formula(builder_ctx, product_page):
    _page, link, _action = product_page

    elements.update_element(
        builder_ctx["ctx"],
        link.id,
        ElementEdits(
            link_page_parameters=[{"name": "id", "value": "get('page_parameter.x')"}]
        ),
    )

    # The home page has no parameter x, so the formula is refused and the previous
    # value stays.
    assert _stored(link) == [("id", "'1'")]

    elements.update_element(
        builder_ctx["ctx"],
        link.id,
        ElementEdits(
            link_page_parameters=[{"name": "id", "value": "concat('4', '2')"}]
        ),
    )

    assert _stored(link) == [("id", "concat('4', '2')")]


@pytest.mark.django_db
def test_update_element_refuses_link_parameters_the_page_does_not_take(
    builder_ctx, product_page
):
    _page, link, _action = product_page

    with pytest.raises(ToolInputError, match="unknown: slug"):
        elements.update_element(
            builder_ctx["ctx"],
            link.id,
            ElementEdits(link_page_parameters=[{"name": "slug", "value": "x"}]),
        )

    assert _stored(link) == [("id", "'1'")]


@pytest.mark.django_db
def test_update_page_lists_a_table_link_column_its_new_parameters_break(
    data_fixture, builder_ctx, product_page
):
    page, _link, _action = product_page
    table = data_fixture.create_builder_table_element(
        page=builder_ctx["page"],
        fields=[
            {
                "name": "Open",
                "type": "link",
                "config": {
                    "link_name": "'Open'",
                    "navigation_type": "page",
                    "navigate_to_page_id": page.id,
                    "page_parameters": [{"name": "id", "value": "'1'"}],
                },
            }
        ],
    )

    result = pages.update_page(
        builder_ctx["ctx"], page.id, PageChanges(path="/products/:slug")
    )

    (column,) = [
        n for n in result["navigations_to_fix"] if n["type"] == "table link column"
    ]
    assert column["element_id"] == table.id
    assert column["column_name"] == "Open"
    assert column["page_parameters"] == ["id"]


def _menu_item_to(data_fixture, builder_ctx, page, page_parameters):
    menu = data_fixture.create_builder_menu_element(page=builder_ctx["page"])
    item = MenuItemElement.objects.create(
        variant="link",
        type="link",
        name="Detail",
        navigation_type="page",
        navigate_to_page=page,
        page_parameters=page_parameters,
        menu_item_order=0,
    )
    menu.menu_items.add(item)
    return menu, item


@pytest.mark.django_db
def test_update_page_lists_a_menu_item_still_giving_a_removed_parameter(
    data_fixture, builder_ctx, product_page
):
    page, _link, _action = product_page
    menu, item = _menu_item_to(
        data_fixture, builder_ctx, page, [{"name": "id", "value": "'1'"}]
    )

    result = pages.update_page(
        builder_ctx["ctx"], page.id, PageChanges(path="/products")
    )

    (entry,) = [n for n in result["navigations_to_fix"] if n["type"] == "menu item"]
    assert entry["element_id"] == menu.id
    assert entry["uid"] == str(item.uid)
    assert entry["page_parameters"] == ["id"]
    assert "editor" in entry["fix"]


@pytest.mark.django_db
def test_update_page_lists_a_menu_item_missing_a_new_parameter(
    data_fixture, builder_ctx, product_page
):
    page, _link, _action = product_page
    menu, _item = _menu_item_to(
        data_fixture, builder_ctx, page, [{"name": "id", "value": "'1'"}]
    )

    result = pages.update_page(
        builder_ctx["ctx"], page.id, PageChanges(path="/products/:slug")
    )

    (entry,) = [n for n in result["navigations_to_fix"] if n["type"] == "menu item"]
    assert entry["element_id"] == menu.id
    assert "slug" in entry["fix"]


@pytest.mark.django_db
def test_update_page_lists_no_menu_item_that_fits(
    data_fixture, builder_ctx, product_page
):
    page, _link, _action = product_page
    _menu_item_to(data_fixture, builder_ctx, page, [{"name": "id", "value": "'1'"}])

    result = pages.update_page(builder_ctx["ctx"], page.id, PageChanges(name="Item"))

    assert "navigations_to_fix" not in result
