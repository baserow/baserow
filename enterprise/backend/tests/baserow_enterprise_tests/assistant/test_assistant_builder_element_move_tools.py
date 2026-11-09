"""
Unit tests for the builder assistant move_elements tool.
"""

from django.db import transaction

import pytest
from pydantic import ValidationError

from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import Element
from baserow_enterprise.assistant.tools.builder.tools import (
    create_display_elements,
    create_layout_elements,
    move_elements,
)
from baserow_enterprise.builder.tools import helpers
from baserow_enterprise.builder.tools.types import (
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
        "baserow_enterprise.assistant.tools.builder.agents.repair_builder_formula_errors",
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
def test_move_element_to_end_keeps_the_request_cache(data_fixture):
    from django.test import override_settings

    from baserow.core.cache import local_cache

    ctx, page, ref_to_id_map = _create_two_headings(data_fixture)

    with override_settings(BASEROW_USE_LOCAL_CACHE=True), local_cache.context():
        local_cache.get("kept", lambda: "value")
        move_elements(
            ctx,
            page_id=page.id,
            moves=[ElementMove(element_id=ref_to_id_map["h1"], before_id=None)],
            thought="move to end",
        )
        assert local_cache.get("kept", lambda: "rebuilt") == "value"

    page.refresh_from_db()
    page.assert_reference(
        {
            "0": "Second-1",
            "Second-1": {"next": {"": ["First-0"]}},
            "First-0": {},
        }
    )


@pytest.mark.django_db(transaction=True)
def test_move_after_a_failed_move_reads_the_saved_graph(data_fixture, monkeypatch):
    from django.test import override_settings

    from baserow.core.cache import local_cache
    from baserow_enterprise.builder.tools import helpers

    ctx, page, ref_to_id_map = _create_two_headings(data_fixture)
    move_element = helpers.move_element
    calls = []

    def fail_the_first_move(*args, **kwargs):
        element = move_element(*args, **kwargs)
        calls.append(element.id)
        if len(calls) == 1:
            raise ValueError("failed after moving")
        return element

    monkeypatch.setattr(helpers, "move_element", fail_the_first_move)
    move_to_end = ElementMove(element_id=ref_to_id_map["h1"], before_id=None)

    with override_settings(BASEROW_USE_LOCAL_CACHE=True), local_cache.context():
        result = move_elements(
            ctx, page_id=page.id, moves=[move_to_end, move_to_end], thought="t"
        )

    assert len(result["errors"]) == 1
    page.refresh_from_db()
    page.assert_reference(
        {
            "0": "Second-1",
            "Second-1": {"next": {"": ["First-0"]}},
            "First-0": {},
        }
    )


@pytest.mark.django_db(transaction=True)
def test_moves_keep_an_element_added_between_them(data_fixture, monkeypatch):
    from threading import Thread

    from django.db import connection
    from django.test import override_settings

    from baserow.contrib.builder.elements.registries import element_type_registry
    from baserow.contrib.builder.elements.service import ElementService
    from baserow.core.cache import local_cache

    ctx, page, ref_to_id_map = _create_two_headings(data_fixture)
    move_element = helpers.move_element
    added = []

    def add_heading_from_another_connection():
        try:
            added.append(
                ElementService().create_element(
                    ctx.deps.user,
                    element_type_registry.get("heading"),
                    page.__class__.objects.get(id=page.id),
                    value="'Added'",
                )
            )
        finally:
            connection.close()

    calls = []

    def add_before_the_second_move(*args, **kwargs):
        # The first move has committed and released its lock by now.
        calls.append(1)
        if len(calls) == 2:
            thread = Thread(target=add_heading_from_another_connection)
            thread.start()
            thread.join(timeout=10)
        return move_element(*args, **kwargs)

    monkeypatch.setattr(helpers, "move_element", add_before_the_second_move)

    with override_settings(BASEROW_USE_LOCAL_CACHE=True), local_cache.context():
        result = move_elements(
            ctx,
            page_id=page.id,
            moves=[
                ElementMove(element_id=ref_to_id_map["h1"], before_id=None),
                ElementMove(element_id=ref_to_id_map["h2"], before_id=None),
            ],
            thought="t",
        )

    assert "errors" not in result
    page.refresh_from_db()
    assert str(added[0].id) in page.graph


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
        helpers.move_element(ctx.deps.user, page, move)

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


@pytest.mark.django_db(transaction=True)
def test_children_keep_their_order_when_created_and_moved(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home", path="/home")
    ctx = make_test_ctx(user, workspace, create_fake_tool_helpers())

    layout = create_layout_elements(
        ctx,
        page_id=page.id,
        elements=[
            LayoutElementCreate(ref="box", type="simple_container"),
            LayoutElementCreate(ref="top", type="header"),
        ],
        thought="test",
    )["ref_to_id_map"]
    create_display_elements(
        ctx,
        page_id=page.id,
        elements=[
            DisplayElementCreate(
                ref=value, type="heading", value=value, parent_element=layout["box"]
            )
            for value in ("First", "Second")
        ]
        + [
            DisplayElementCreate(
                ref=value, type="button", value=value, parent_element=layout["top"]
            )
            for value in ("One", "Two")
        ],
        thought="test",
    )
    loose = create_display_elements(
        ctx,
        page_id=page.id,
        elements=[DisplayElementCreate(ref="h", type="heading", value="Third")],
        thought="test",
    )["ref_to_id_map"]["h"]
    move_elements(
        ctx,
        page_id=page.id,
        moves=[ElementMove(element_id=loose, parent_element_id=layout["box"])],
        thought="test",
    )

    def children(element_id):
        container = Element.objects.get(id=element_id)
        container.page.reload_graph()
        return [
            child.specific.value["formula"]
            for child in container.page.get_graph().get_children(element_id)
        ]

    assert children(layout["box"]) == ["'First'", "'Second'", "'Third'"]
    assert children(layout["top"]) == ["'One'", "'Two'"]
