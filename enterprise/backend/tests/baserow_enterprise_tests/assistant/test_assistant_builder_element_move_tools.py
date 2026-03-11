"""
Unit tests for the builder assistant move_elements tool.
"""

import pytest

from baserow.contrib.builder.elements.handler import ElementHandler
from baserow_enterprise.assistant.tools.builder.tools import (
    create_display_elements,
    create_layout_elements,
    move_elements,
)
from baserow_enterprise.assistant.tools.builder.types import (
    DisplayElementCreate,
    ElementMove,
    LayoutElementCreate,
)

from .utils import create_fake_tool_helpers, make_test_ctx


@pytest.fixture(autouse=True)
def mock_formula_generators(monkeypatch):
    """Mock all formula generation to avoid LLM requirement in tests."""

    def noop(*args, **kwargs):
        return []

    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.builder.agents.update_element_formulas",
        noop,
    )
    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.builder.agents.update_data_source_formulas",
        noop,
    )
    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.builder.agents.update_workflow_action_formulas",
        noop,
    )
    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.builder.agents.update_single_element_formulas",
        noop,
    )
    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.builder.agents.update_single_data_source_formulas",
        noop,
    )


def _create_two_headings(data_fixture):
    """Helper: create a page with two heading elements, return (ctx, page, id1, id2)."""
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(ref="h1", type="heading", value="First", level=1),
            DisplayElementCreate(ref="h2", type="heading", value="Second", level=2),
        ],
        thought="test",
    )

    id1 = result["ref_to_id_map"]["h1"]
    id2 = result["ref_to_id_map"]["h2"]
    return ctx, page, id1, id2


@pytest.mark.django_db(transaction=True)
def test_move_element_before_another(data_fixture):
    ctx, page, id1, id2 = _create_two_headings(data_fixture)

    # Move h2 before h1
    result = move_elements(
        ctx,
        page_id=page.id,
        moves=[ElementMove(element_id=id2, before_id=id1)],
        thought="reorder",
    )

    assert len(result["moved_elements"]) == 1
    assert result["moved_elements"][0]["element_id"] == id2
    assert "errors" not in result

    # Verify order: h2 should now come before h1
    elements = list(ElementHandler().get_elements(page))
    ids_in_order = [e.id for e in elements]
    assert ids_in_order.index(id2) < ids_in_order.index(id1)


@pytest.mark.django_db(transaction=True)
def test_move_element_to_end(data_fixture):
    ctx, page, id1, id2 = _create_two_headings(data_fixture)

    # Move h1 to end (before_id=None)
    result = move_elements(
        ctx,
        page_id=page.id,
        moves=[ElementMove(element_id=id1, before_id=None)],
        thought="move to end",
    )

    assert len(result["moved_elements"]) == 1
    assert result["moved_elements"][0]["element_id"] == id1

    # h1 should now be after h2
    elements = list(ElementHandler().get_elements(page))
    ids_in_order = [e.id for e in elements]
    assert ids_in_order.index(id1) > ids_in_order.index(id2)


@pytest.mark.django_db(transaction=True)
def test_move_element_into_container(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    # Create a column container
    layout_result = create_layout_elements(
        ctx,
        page_id=page.id,
        elements=[LayoutElementCreate(ref="cols", type="column", column_amount=2)],
        thought="test",
    )
    col_id = layout_result["ref_to_id_map"]["cols"]

    # Create a heading at root level
    display_result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(ref="h1", type="heading", value="Hello", level=1),
        ],
        thought="test",
    )
    h1_id = display_result["ref_to_id_map"]["h1"]

    # Move heading into column container, slot "1"
    result = move_elements(
        ctx,
        page_id=page.id,
        moves=[
            ElementMove(
                element_id=h1_id,
                parent_element_id=col_id,
                place_in_container="1",
            )
        ],
        thought="move into container",
    )

    assert len(result["moved_elements"]) == 1
    moved = result["moved_elements"][0]
    assert moved["element_id"] == h1_id
    assert moved["parent_element_id"] == col_id
    assert moved["place_in_container"] == "1"


@pytest.mark.django_db(transaction=True)
def test_move_element_to_root(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    tool_helpers = create_fake_tool_helpers()
    ctx = make_test_ctx(user, workspace, tool_helpers)

    # Create column + child heading inside it
    layout_result = create_layout_elements(
        ctx,
        page_id=page.id,
        elements=[LayoutElementCreate(ref="cols", type="column", column_amount=2)],
        thought="test",
    )
    col_id = layout_result["ref_to_id_map"]["cols"]

    display_result = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(
                ref="h1",
                type="heading",
                value="Inside",
                level=1,
                parent_element="cols",
                place_in_container="0",
            ),
        ],
        thought="test",
    )
    h1_id = display_result["ref_to_id_map"]["h1"]

    # Verify it's inside the container
    el = ElementHandler().get_element(h1_id)
    assert el.parent_element_id == col_id

    # Move it to root (parent_element_id=None)
    result = move_elements(
        ctx,
        page_id=page.id,
        moves=[ElementMove(element_id=h1_id, parent_element_id=None)],
        thought="move to root",
    )

    assert len(result["moved_elements"]) == 1
    moved = result["moved_elements"][0]
    assert moved["element_id"] == h1_id
    assert moved["parent_element_id"] is None
