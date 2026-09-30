"""
Unit tests for the builder assistant move_elements tool.
"""

from django.db import transaction

import pytest
from pydantic import ValidationError

from baserow.contrib.builder.elements.handler import ElementHandler
from baserow_enterprise.assistant.tools.builder import helpers
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

    return ctx, page, result["ref_to_id_map"]


@pytest.mark.django_db(transaction=True)
def test_move_element_before_another(data_fixture):
    ctx, page, ref_to_id_map = _create_two_headings(data_fixture)

    # Move h2 before h1
    move_elements(
        ctx,
        page_id=page.id,
        moves=[
            ElementMove(element_id=ref_to_id_map["h2"], before_id=ref_to_id_map["h1"])
        ],
        thought="reorder",
    )

    page.refresh_from_db()
    page.assert_reference(
        {
            "0": "Second-1",
            "First-0": {},
            "Second-1": {"next": {"": ["First-0"]}},
        }
    )


@pytest.mark.django_db(transaction=True)
def test_move_element_to_end(data_fixture):
    ctx, page, ref_to_id_map = _create_two_headings(data_fixture)

    # Move h1 to end (before_id=None)
    move_elements(
        ctx,
        page_id=page.id,
        moves=[ElementMove(element_id=ref_to_id_map["h1"], before_id=None)],
        thought="move to end",
    )

    page.refresh_from_db()
    page.assert_reference(
        {
            "0": "Second-1",
            "Second-1": {"next": {"": ["First-0"]}},
            "First-0": {},
        }
    )


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
    move_elements(
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

    page.refresh_from_db()
    page.assert_reference(
        {
            "0": "column-0",
            "column-0": {"children": {"1": ["Hello-1"]}},
            "Hello-1": {},
        }
    )


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
    move_elements(
        ctx,
        page_id=page.id,
        moves=[ElementMove(element_id=h1_id, parent_element_id=None)],
        thought="move to root",
    )

    page.refresh_from_db()
    page.assert_reference(
        {
            "0": "column-0",
            "column-0": {"next": {"": ["Inside-1"]}},
            "Inside-1": {},
        }
    )


def test_element_move_rejects_place_in_container_without_parent():
    # The customer corruption behind BASEROW-SAAS-BACKEND-16Z: a root-level move
    # that kept the column slot. The schema now refuses it so the model gets an
    # actionable message before the tool runs.
    with pytest.raises(ValidationError) as exc_info:
        ElementMove(element_id=1, parent_element_id=None, place_in_container="0")

    assert "parent_element_id" in str(exc_info.value)

    # A slot together with a parent is still fine.
    ElementMove(element_id=1, parent_element_id=2, place_in_container="0")


@pytest.mark.django_db(transaction=True)
def test_move_element_helper_drops_place_in_container_without_parent(
    data_fixture,
):
    ctx, page, ref_to_id_map = _create_two_headings(data_fixture)
    h1_id, h2_id = ref_to_id_map["h1"], ref_to_id_map["h2"]

    # Bypass the schema validator, like a direct caller would, and move h1 to
    # the end of the page while keeping a slot.
    move = ElementMove.model_construct(
        element_id=h1_id,
        before_id=None,
        parent_element_id=None,
        place_in_container="0",
    )

    # The tool wraps each move in a transaction (the helper locks the row).
    with transaction.atomic():
        helpers.move_element(ctx.deps.user, move)

    page.refresh_from_db()
    # h1 is last, on the default output; no stray `next["0"]` edge.
    page.assert_reference(
        {
            "0": "Second-1",
            "Second-1": {"next": {"": ["First-0"]}},
            "First-0": {},
        }
    )


@pytest.mark.django_db(transaction=True)
def test_create_display_element_without_parent_ignores_place_in_container(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")

    ctx = make_test_ctx(user, workspace, create_fake_tool_helpers())

    # A root-level element that carries a slot (no parent): the slot is
    # dropped instead of being forwarded as a south/north output.
    create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(ref="h1", type="heading", value="First", level=1),
            DisplayElementCreate(
                ref="h2",
                type="heading",
                value="Second",
                level=1,
                place_in_container="0",
            ),
        ],
        thought="test",
    )

    page.refresh_from_db()
    page.assert_reference(
        {
            "0": "First-0",
            "First-0": {"next": {"": ["Second-1"]}},
            "Second-1": {},
        }
    )
