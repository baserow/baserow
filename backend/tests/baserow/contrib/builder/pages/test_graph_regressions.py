"""
Regression tests for every graph corruption class that
`ElementHandler.heal_corrupted_graph` repairs.

Each corruption in this file was observed in production (or produced by a
since-guarded write path) before the page row lock and the graph write guards
existed. The healer — invoked from the elements list GET — must repair each of
them so that a page corrupted by pre-guard history loads, traverses, and
accepts writes again. One section per corruption class:

- orphans: element rows missing from the graph (created without a graph
  insert, e.g. by old code during a non-zero-downtime deploy).
- stale points: graph entries whose element row was hard-deleted.
- self-references: a point listing itself as its own next/child.
- dangling references: next/children ids with no corresponding graph entry.
- cycles: a reference chain that loops back onto an ancestor, making an
  element its own transitive parent (the customer corruption that hung
  imports and previews).
- converging references: two chains "merged" onto one element (the aftermath
  of pre-guard double inserts); the write guards fail closed on such elements
  until the heal strips the surplus reference.
- detached points: live elements keyed in the graph but unreachable from the
  root (invisible and undeletable).
- invalid children edges: children stored under a place their element cannot
  have (an unknown container place, or any children on a non-container) —
  reachable and consistent-looking, but never rendered.
- composites: several classes at once, including the anonymized real-world
  customer graph shape.

Each section pairs two kinds of test:

- healing tests prove the corruption, once present, is repaired by
  `heal_corrupted_graph`; and
- `test_corruption_prevented_*` companions prove the corruption's historical
  producer no longer works: the write is either rejected (the graph write
  guards fail closed) or made safe (the page row lock refreshes stale
  in-memory state), and the section's corruption detector stays empty.
"""

from unittest.mock import patch
from unittest.mock import patch as mock_patch

import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.builder.elements.exceptions import ElementMoveNotAllowed
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import ColumnElement, Element
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.elements.service import ElementService
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.healing_handler import PageHealingHandler
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.pages.service import PageService
from baserow.core.cache import local_cache
from baserow.core.graph.exceptions import GraphPointReferencePointInvalid
from baserow.core.graph.handler import BaseGraphHandler
from baserow.core.graph.types import GraphPointPosition
from baserow.core.trash.exceptions import TrashItemRestorationDisallowed
from baserow.core.trash.handler import TrashHandler

# ==================
# -- Steady state --
# ==================


@pytest.mark.django_db
def test_heal_corrupted_graph_is_a_noop_when_graph_is_consistent(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_fixture.create_builder_heading_element(page=page)

    page.refresh_from_db(fields=["graph"])
    before = dict(page.graph)

    assert PageHandler().heal_corrupted_graph(page) == {}

    page.refresh_from_db(fields=["graph"])
    assert page.graph == before


# ==================================================
# -- Orphans: element rows missing from the graph --
# ==================================================


@pytest.mark.django_db
def test_heal_corrupted_graph_appends_to_unshared_page_root(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    element1 = data_fixture.create_builder_heading_element(page=page)

    # An element in the DB but missing from the graph (created without a graph
    # insert, mimicking an old-code write during a non-zero-downtime deploy).
    orphan = ElementHandler().create_element(
        element_type_registry.get("heading"), page=page
    )
    page.refresh_from_db(fields=["graph"])
    assert str(orphan.id) not in page.graph

    patch = PageHandler().heal_corrupted_graph(page)

    # The patch contains only the entries that changed: the orphan's new entry and
    # the element it was linked after.
    assert patch == {
        str(element1.id): {"next": {"": [orphan.id]}},
        str(orphan.id): {},
    }

    page.refresh_from_db(fields=["graph"])
    # The orphan is appended to the end of the (unshared) page's root chain.
    assert page.graph == {
        "0": element1.id,
        str(element1.id): {"next": {"": [orphan.id]}},
        str(orphan.id): {},
    }


@pytest.mark.django_db
def test_heal_corrupted_graph_appends_to_first_shared_element_on_shared_page(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    shared_page = page.builder.shared_page

    # The first shared element (a Header container) lives at the root of the
    # shared page.
    header = ElementService().create_element(
        user, element_type_registry.get("header"), page=shared_page
    )

    # A regular element on the shared page that's missing from the graph.
    orphan = ElementHandler().create_element(
        element_type_registry.get("heading"), page=shared_page
    )
    shared_page.refresh_from_db(fields=["graph"])
    assert str(orphan.id) not in shared_page.graph

    patch = PageHandler().heal_corrupted_graph(shared_page)

    # The patch carries the orphan and the header (whose children changed).
    assert str(orphan.id) in patch
    assert str(header.id) in patch

    shared_page.refresh_from_db(fields=["graph"])
    # The orphan is appended to the end of the first shared element (the header).
    assert shared_page.graph[str(header.id)]["children"][""] == [orphan.id]


@pytest.mark.django_db
def test_corruption_prevented_stale_write_cannot_drop_elements(data_fixture):
    # The orphan producer: two overlapping requests each read the page, and
    # the second whole-document graph write silently discarded the first
    # request's insert (lost update), leaving that element in the DB but not
    # in the graph. The page row lock now refreshes stale in-memory state
    # before every mutation, so both inserts survive.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_fixture.create_builder_heading_element(page=page)
    heading = element_type_registry.get("heading")

    # Two "requests", each with its own page object loaded before either
    # writes. Clearing the request-local cache between operations keeps the
    # two from sharing an in-memory graph, like separate workers would.
    page_a = Page.objects.get(id=page.id)
    page_b = Page.objects.get(id=page.id)

    local_cache.clear()
    e2 = ElementService().create_element(user, heading, page=page_a)
    local_cache.clear()
    e3 = ElementService().create_element(user, heading, page=page_b)
    local_cache.clear()

    page.refresh_from_db(fields=["graph"])
    # Pre-lock, page_b's stale write dropped e2's entry. Both must be keyed.
    assert str(e2.id) in page.graph
    assert str(e3.id) in page.graph
    assert BaseGraphHandler.find_dangling_reference_ids(page.graph) == set()
    assert PageHandler().heal_corrupted_graph(page) == {}


# ===========================================================
# -- Stale points: graph entries whose element row is gone --
# ===========================================================


@pytest.mark.django_db
def test_heal_prunes_stale_point_for_hard_deleted_element(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    # A 3-element root chain through the graph: e1 → e2 → e3.
    heading = element_type_registry.get("heading")
    e1 = ElementService().create_element(user, heading, page=page)
    e2 = ElementService().create_element(user, heading, page=page)
    e3 = ElementService().create_element(user, heading, page=page)

    page.refresh_from_db(fields=["graph"])
    assert str(e2.id) in page.graph

    # Simulate old code hard-deleting the middle element's row without touching
    # the graph: the graph now references a point with no DB row ("stale point").
    Element.objects.filter(id=e2.id).delete()

    patch = PageHandler().heal_corrupted_graph(page)

    page.refresh_from_db(fields=["graph"])
    # The stale point is spliced out and the chain re-stitched: e1 → e3.
    assert str(e2.id) not in page.graph
    assert page.graph == {
        "0": e1.id,
        str(e1.id): {"next": {"": [e3.id]}},
        str(e3.id): {},
    }
    # The relinked predecessor is carried in the patch.
    assert patch == {str(e1.id): {"next": {"": [e3.id]}}}


@pytest.mark.django_db
def test_heal_prunes_stale_point_and_does_not_raise_on_traversal(data_fixture):
    """A stale point would make graph traversal resolve a missing element and
    raise; after healing, the ordered traversal succeeds."""

    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    heading = element_type_registry.get("heading")
    e1 = ElementService().create_element(user, heading, page=page)
    e2 = ElementService().create_element(user, heading, page=page)

    Element.objects.filter(id=e1.id).delete()  # the root point is now stale

    PageHandler().heal_corrupted_graph(page)

    page.refresh_from_db(fields=["graph"])
    # The surviving element is promoted to root; traversal resolves cleanly.
    assert page.graph == {"0": e2.id, str(e2.id): {}}
    graph = page.get_graph()
    assert graph.get_point(e2.id).id == e2.id


@pytest.mark.django_db
def test_corruption_prevented_deletion_leaves_no_stale_entries(data_fixture):
    # Stale points were written by code that deleted element rows without
    # touching the graph. The supported deletion path (service → trash) must
    # remove the graph entry and re-stitch the chain in the same operation.
    # (Out-of-band hard deletes can't be guarded — the heal covers those.)
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    heading = element_type_registry.get("heading")
    e1 = ElementService().create_element(user, heading, page=page)
    e2 = ElementService().create_element(user, heading, page=page)
    e3 = ElementService().create_element(user, heading, page=page)

    ElementService().delete_element(
        user, ElementHandler().get_element_for_update(e2.id)
    )

    page.refresh_from_db(fields=["graph"])
    assert page.graph == {
        "0": e1.id,
        str(e1.id): {"next": {"": [e3.id]}},
        str(e3.id): {},
    }
    # The graph keys exactly the live rows: nothing stale, nothing dangling.
    db_ids = set(Element.objects.filter(page=page).values_list("id", flat=True))
    assert {int(k) for k in page.graph if k != "0"} == db_ids
    assert BaseGraphHandler.find_dangling_reference_ids(page.graph) == set()


# =====================
# -- Self-references --
# =====================


@pytest.mark.django_db
def test_heal_strips_self_referencing_point(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    heading = element_type_registry.get("heading")
    e1 = ElementService().create_element(user, heading, page=page)
    e2 = ElementService().create_element(user, heading, page=page)

    # Simulate the real-world corruption: the tail element lists itself as its
    # own `next`. There is no DB<->graph drift, so only the self-reference scan
    # can detect this.
    page.graph[str(e2.id)]["next"] = {"": [e2.id]}
    page.save(update_fields=["graph"])

    patch = PageHandler().heal_corrupted_graph(page)

    page.refresh_from_db(fields=["graph"])
    assert page.graph == {
        "0": e1.id,
        str(e1.id): {"next": {"": [e2.id]}},
        str(e2.id): {},
    }
    # The stripped entry is carried in the patch so clients can shallow-merge.
    assert patch == {str(e2.id): {}}


@pytest.mark.django_db
def test_corruption_prevented_double_insert_at_reference_is_rejected(data_fixture):
    # The self-reference producer: inserting an element south of the very
    # point that already references it made the insert read the element as
    # its own "old successor" and write next -> itself. The write guard now
    # rejects inserting any element that still has an incoming reference.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    e1 = data_fixture.create_builder_heading_element(page=page)
    e2 = data_fixture.create_builder_heading_element(page=page)

    page.refresh_from_db(fields=["graph"])
    before = dict(page.graph)

    with pytest.raises(GraphPointReferencePointInvalid):
        page.get_graph().insert(e2, e1, GraphPointPosition.SOUTH, "")

    page.refresh_from_db(fields=["graph"])
    assert page.graph == before
    assert BaseGraphHandler.find_self_referencing_point_ids(page.graph) == set()


# =========================
# -- Dangling references --
# =========================


@pytest.mark.django_db
def test_heal_strips_dangling_next_and_children_references(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    column = element_type_registry.get("column")
    heading = element_type_registry.get("heading")
    container = ElementService().create_element(user, column, page=page)
    child = ElementService().create_element(
        user,
        heading,
        page=page,
        reference_element_id=container.id,
        position=GraphPointPosition.CHILD,
        place_in_container="0",
    )

    page.refresh_from_db(fields=["graph"])
    missing_next_id = max(container.id, child.id) + 1000
    missing_child_id = missing_next_id + 1
    page.graph[str(child.id)]["next"] = {"": [missing_next_id]}
    page.graph[str(container.id)]["children"]["1"] = [missing_child_id]
    page.save(update_fields=["graph"])

    patch = PageHandler().heal_corrupted_graph(page)

    page.refresh_from_db(fields=["graph"])
    assert page.graph == {
        "0": container.id,
        str(container.id): {"children": {"0": [child.id]}},
        str(child.id): {},
    }
    assert patch == {
        str(container.id): {"children": {"0": [child.id]}},
        str(child.id): {},
    }


@pytest.mark.django_db
def test_corruption_prevented_stale_write_cannot_resurrect_deleted_reference(
    data_fixture,
):
    # The dangling-reference producer: a request that loaded the page before
    # an element was deleted would, on its next whole-document write, put the
    # reference to the deleted element back (lost update). The page row lock
    # refreshes the stale in-memory graph before mutating, so the deletion
    # survives a subsequent write from the stale request.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    heading = element_type_registry.get("heading")
    e1 = ElementService().create_element(user, heading, page=page)
    e2 = ElementService().create_element(user, heading, page=page)
    e3 = ElementService().create_element(user, heading, page=page)

    # A second "request" loads the page while e2 still exists.
    page_stale = Page.objects.get(id=page.id)

    local_cache.clear()
    ElementService().delete_element(
        user, ElementHandler().get_element_for_update(e2.id)
    )

    local_cache.clear()
    # The stale request performs a graph write computed from its pre-delete
    # in-memory state.
    page_stale.get_graph().move(
        ElementHandler().get_element(e3.id),
        ElementHandler().get_element(e1.id),
        GraphPointPosition.SOUTH,
        "",
    )

    page.refresh_from_db(fields=["graph"])
    # Pre-lock, the stale write resurrected e1 -> e2 with e2's entry gone — a
    # dangling reference. The deletion must survive.
    assert str(e2.id) not in page.graph
    assert page.graph == {
        "0": e1.id,
        str(e1.id): {"next": {"": [e3.id]}},
        str(e3.id): {},
    }
    assert BaseGraphHandler.find_dangling_reference_ids(page.graph) == set()


@pytest.mark.django_db
def test_corruption_prevented_move_relative_to_unkeyed_reference_is_rejected(
    data_fixture,
):
    # The reference row exists but has no graph entry (an unhealed orphan, or
    # deleted by a concurrent transaction after this request fetched it).
    # Proceeding used to KeyError midway; the write guard rejects it cleanly.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    e1 = data_fixture.create_builder_heading_element(page=page)
    orphan = ElementHandler().create_element(
        element_type_registry.get("heading"), page=page
    )

    page.refresh_from_db(fields=["graph"])
    before = dict(page.graph)

    with pytest.raises(GraphPointReferencePointInvalid):
        ElementService().move_element(
            user,
            page,
            ElementHandler().get_element_for_update(e1.id),
            "",
            orphan.id,
            GraphPointPosition.SOUTH,
        )

    page.refresh_from_db(fields=["graph"])
    assert page.graph == before


@pytest.mark.django_db
def test_corruption_prevented_restore_with_unkeyed_reference_is_rejected(
    data_fixture,
):
    # A trashed element records its position relative to a reference; if that
    # reference has meanwhile left the graph, re-inserting would write a
    # reference no traversal can follow. The restore refuses instead.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    heading = element_type_registry.get("heading")
    e1 = ElementService().create_element(user, heading, page=page)
    e2 = ElementService().create_element(user, heading, page=page)

    ElementService().delete_element(
        user, ElementHandler().get_element_for_update(e2.id)
    )

    # Simulate divergence: e1 (the recorded reference) loses its graph entry.
    page.refresh_from_db(fields=["graph"])
    page.graph = {}
    page.save(update_fields=["graph"])

    # The restore arrives as its own request, with no shared in-memory graph.
    local_cache.clear()

    with pytest.raises(TrashItemRestorationDisallowed):
        TrashHandler.restore_item(user, "builder_element", e2.id)


# ==========================================================
# -- Cycles: an element becomes its own transitive parent --
# ==========================================================


def _corrupt_page_with_ancestor_cycle(data_fixture, page):
    """
    Replicate a customer corruption: a container's child chain loops back onto
    the container's predecessor. The cycle (heading -> column -> choice1 ->
    choice2 -> heading) crosses a parent/child boundary, so the column resolves
    as its own parent while every point stays reachable from the root — no
    direct self-reference, nothing dangling, nothing detached.
    """

    heading = data_fixture.create_builder_heading_element(page=page)
    column = data_fixture.create_builder_column_element(page=page, column_amount=2)
    choice1 = data_fixture.create_builder_choice_element(page=page)
    choice2 = data_fixture.create_builder_choice_element(page=page)

    page.graph = {
        "0": heading.id,
        str(heading.id): {"next": {"": [column.id]}},
        str(column.id): {"children": {"0": [choice1.id]}},
        str(choice1.id): {"next": {"": [choice2.id]}},
        str(choice2.id): {"next": {"": [heading.id]}},
    }
    page.save(update_fields=["graph"])
    return heading, column, choice1, choice2


@pytest.mark.django_db
def test_heal_corrupted_graph_breaks_reachable_ancestor_cycle(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    heading, column, choice1, choice2 = _corrupt_page_with_ancestor_cycle(
        data_fixture, page
    )

    # The corruption makes the column its own parent.
    assert column.parent_element_id == column.id

    patch = PageHandler().heal_corrupted_graph(page)

    # Only the cycle-closing reference (choice2 -> heading) is stripped.
    assert patch == {str(choice2.id): {}}
    page.refresh_from_db(fields=["graph"])
    assert page.graph == {
        "0": heading.id,
        str(heading.id): {"next": {"": [column.id]}},
        str(column.id): {"children": {"0": [choice1.id]}},
        str(choice1.id): {"next": {"": [choice2.id]}},
        str(choice2.id): {},
    }

    # Ancestry now resolves sanely for every element.
    assert heading.parent_element_id is None
    assert column.parent_element_id is None
    assert choice1.parent_element_id == column.id
    assert choice2.parent_element_id == column.id

    # A healed graph is a no-op on the next reconcile.
    assert PageHandler().heal_corrupted_graph(page) == {}


@pytest.mark.django_db
def test_ancestor_walks_terminate_on_cyclic_graph(data_fixture):
    # Even when the graph has not been healed, the parent_element_id walks
    # (ancestor lookups and import context resolution) must terminate instead
    # of looping forever on a cyclic graph.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    heading, column, choice1, choice2 = _corrupt_page_with_ancestor_cycle(
        data_fixture, page
    )
    assert column.parent_element_id == column.id

    ancestors = ElementHandler().get_ancestors(choice1, page)
    assert [ancestor.id for ancestor in ancestors] == [column.id]

    element_map = {
        element.id: element for element in [heading, column, choice1, choice2]
    }
    context = ElementHandler().get_import_context_addition(
        choice1.id, element_map=element_map
    )
    assert isinstance(context, dict)


@pytest.mark.django_db
def test_corruption_prevented_move_relative_to_own_descendant_is_rejected(data_fixture):
    # A stale client (second tab, not-yet-synced operation) can ask to move a
    # container relative to an element that is meanwhile inside that
    # container. Accepting it would loop the subtree back onto its ancestor.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    column = data_fixture.create_builder_column_element(page=page, column_amount=2)
    child = data_fixture.create_builder_heading_element(page=page)

    page.graph = {
        "0": column.id,
        str(column.id): {"children": {"0": [child.id]}},
        str(child.id): {},
    }
    page.save(update_fields=["graph"])
    before = dict(page.graph)

    with pytest.raises(ElementMoveNotAllowed):
        ElementService().move_element(
            user,
            page,
            ElementHandler().get_element_for_update(column.id),
            "",
            child.id,
            GraphPointPosition.SOUTH,
        )

    page.refresh_from_db(fields=["graph"])
    assert page.graph == before
    assert BaseGraphHandler.find_cycle_reference_pairs(page.graph) == set()


@pytest.mark.django_db
def test_corruption_prevented_move_of_ghost_element_is_rejected(data_fixture):
    # A "ghost": the element's graph entry was lost (pre-lock stale write)
    # while a reference to it survived. Moving it used to add a second
    # incoming reference without splicing the survivor — the converging
    # reference / cycle producer found in the customer corruption.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    heading = data_fixture.create_builder_heading_element(page=page)
    column = data_fixture.create_builder_column_element(page=page, column_amount=2)
    field = data_fixture.create_builder_heading_element(page=page)
    ghost = data_fixture.create_builder_choice_element(page=page)

    page.graph = {
        "0": heading.id,
        str(heading.id): {"next": {"": [column.id]}},
        str(column.id): {"children": {"0": [field.id]}},
        str(field.id): {"next": {"": [ghost.id]}},
    }
    page.save(update_fields=["graph"])
    before = dict(page.graph)

    with pytest.raises(GraphPointReferencePointInvalid):
        ElementService().move_element(
            user,
            page,
            ElementHandler().get_element_for_update(ghost.id),
            "",
            heading.id,
            GraphPointPosition.NORTH,
        )

    page.refresh_from_db(fields=["graph"])
    assert page.graph == before
    assert BaseGraphHandler.find_cycle_reference_pairs(page.graph) == set()


# ===============================================================
# -- Converging references: two chains merged onto one element --
# ===============================================================


@pytest.mark.django_db
def test_heal_corrupted_graph_strips_converging_references(data_fixture):
    # Diamond corruption: two chains "merged" onto one element (the aftermath
    # a pre-guard double insert leaves behind). The write guards fail-closed
    # on such elements, so the GET-time heal must resolve the surplus
    # reference to make the element movable again.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    first = data_fixture.create_builder_heading_element(page=page)
    second = data_fixture.create_builder_heading_element(page=page)
    converged = data_fixture.create_builder_heading_element(page=page)

    page.graph = {
        "0": first.id,
        str(first.id): {"next": {"": [converged.id]}},
        str(second.id): {"next": {"": [converged.id]}},
        str(converged.id): {},
    }
    page.save(update_fields=["graph"])

    patch = PageHandler().heal_corrupted_graph(page)
    assert patch

    page.refresh_from_db(fields=["graph"])
    # The root-reachable reference is kept; the surplus one is stripped and
    # its (now detached) source is re-attached at the bottom of the page.
    assert page.graph == {
        "0": first.id,
        str(first.id): {"next": {"": [converged.id]}},
        str(converged.id): {"next": {"": [second.id]}},
        str(second.id): {},
    }
    # A healed graph is a no-op on the next reconcile, and the element can be
    # moved again.
    assert PageHandler().heal_corrupted_graph(page) == {}
    ElementService().move_element(
        user,
        page,
        ElementHandler().get_element_for_update(converged.id),
        "",
        second.id,
        GraphPointPosition.SOUTH,
    )


@pytest.mark.django_db
def test_corruption_prevented_double_insert_elsewhere_is_rejected(data_fixture):
    # The converging-reference producer: inserting an already-placed element
    # somewhere else added a second incoming reference while the original one
    # survived (two chains "merged" onto it). The write guard rejects
    # inserting any element that still has an incoming reference.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    e1 = data_fixture.create_builder_heading_element(page=page)
    e2 = data_fixture.create_builder_heading_element(page=page)
    e3 = data_fixture.create_builder_heading_element(page=page)

    page.refresh_from_db(fields=["graph"])
    before = dict(page.graph)

    with pytest.raises(GraphPointReferencePointInvalid):
        page.get_graph().insert(e2, e3, GraphPointPosition.SOUTH, "")

    page.refresh_from_db(fields=["graph"])
    assert page.graph == before
    assert BaseGraphHandler.find_converging_reference_pairs(page.graph) == set()


# =======================================================================
# -- Detached points: keyed in the graph but unreachable from the root --
# =======================================================================


@pytest.mark.django_db
def test_heal_reattaches_detached_element(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    heading = element_type_registry.get("heading")
    e1 = ElementService().create_element(user, heading, page=page)
    e2 = ElementService().create_element(user, heading, page=page)

    # Simulate the real-world "3311" corruption: e2 stays keyed in the graph
    # and its row exists, but nothing references it. There is no DB<->graph
    # drift, so only the reachability scan can detect it.
    page.graph = {"0": e1.id, str(e1.id): {}, str(e2.id): {}}
    page.save(update_fields=["graph"])

    patch = PageHandler().heal_corrupted_graph(page)

    page.refresh_from_db(fields=["graph"])
    # e2 is re-attached as the last element of the page.
    assert page.graph == {
        "0": e1.id,
        str(e1.id): {"next": {"": [e2.id]}},
        str(e2.id): {},
    }
    assert patch == {str(e1.id): {"next": {"": [e2.id]}}}


@pytest.mark.django_db
def test_heal_reattaches_live_children_of_pruned_stale_container(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    column = element_type_registry.get("column")
    heading = element_type_registry.get("heading")
    container = ElementService().create_element(user, column, page=page)
    child = ElementService().create_element(
        user,
        heading,
        page=page,
        parent_element_id=container.id,
        place_in_container="0",
    )

    # Old code hard-deletes the container row without touching the graph. The
    # stale container is pruned, which detaches its live child — the child must
    # be re-attached in the same heal pass, not become a ghost.
    Element.objects.filter(id=container.id).delete()

    PageHandler().heal_corrupted_graph(page)

    page.refresh_from_db(fields=["graph"])
    assert page.graph == {"0": child.id, str(child.id): {}}


@pytest.mark.django_db
def test_heal_reattaches_detached_cycle_component(data_fixture):
    # Two live elements referencing each other with no external reference — a
    # detached component with no head. The cycle pass strips the back-edge and
    # the reattachment pass appends the component at the bottom of the page.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    anchor = data_fixture.create_builder_heading_element(page=page)
    first = data_fixture.create_builder_heading_element(page=page)
    second = data_fixture.create_builder_heading_element(page=page)

    page.graph = {
        "0": anchor.id,
        str(anchor.id): {},
        str(first.id): {"next": {"": [second.id]}},
        str(second.id): {"next": {"": [first.id]}},
    }
    page.save(update_fields=["graph"])

    patch = PageHandler().heal_corrupted_graph(page)
    assert patch

    page.refresh_from_db(fields=["graph"])
    assert page.graph == {
        "0": anchor.id,
        str(anchor.id): {"next": {"": [first.id]}},
        str(first.id): {"next": {"": [second.id]}},
        str(second.id): {},
    }
    assert PageHandler().heal_corrupted_graph(page) == {}


@pytest.mark.django_db
def test_corruption_prevented_move_relative_to_itself_is_rejected(data_fixture):
    # The detached-point producer: moving an element relative to itself
    # spliced it out of its position and then re-inserted it relative to its
    # own (removed) position, leaving it keyed but unreachable — invisible
    # and undeletable. The service and the graph both reject it now.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    e1 = data_fixture.create_builder_heading_element(page=page)
    e2 = data_fixture.create_builder_heading_element(page=page)

    page.refresh_from_db(fields=["graph"])
    before = dict(page.graph)

    with pytest.raises(GraphPointReferencePointInvalid):
        ElementService().move_element(
            user,
            page,
            ElementHandler().get_element_for_update(e2.id),
            "",
            e2.id,
            GraphPointPosition.SOUTH,
        )

    page.refresh_from_db(fields=["graph"])
    assert page.graph == before
    assert BaseGraphHandler.find_unreachable_point_ids(page.graph) == set()


# ==========================================================================
# -- Invalid children edges: children under a place that does not exist --
# ==========================================================================


@pytest.mark.django_db
def test_heal_merges_children_of_unknown_container_place(data_fixture):
    # Children stored under a place the container doesn't have (e.g. written
    # by a pre-guard operation that raced a column-shrink). The graph is
    # reachable and consistent, so only the element-type-aware heal check can
    # find it; the children are merged into a surviving place.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    column = data_fixture.create_builder_column_element(page=page, column_amount=2)
    c1 = data_fixture.create_builder_heading_element(page=page)
    c2 = data_fixture.create_builder_heading_element(page=page)

    page.graph = {
        "0": column.id,
        str(column.id): {"children": {"1": [c1.id], "5": [c2.id]}},
        str(c1.id): {},
        str(c2.id): {},
    }
    page.save(update_fields=["graph"])

    patch = PageHandler().heal_corrupted_graph(page)
    assert patch

    page.refresh_from_db(fields=["graph"])
    # The unknown place "5" is gone; its child is appended to the surviving
    # place's chain.
    assert page.graph == {
        "0": column.id,
        str(column.id): {"children": {"1": [c1.id]}},
        str(c1.id): {"next": {"": [c2.id]}},
        str(c2.id): {},
    }
    assert PageHandler().heal_corrupted_graph(page) == {}


@pytest.mark.django_db
def test_heal_strips_children_edge_on_non_container(data_fixture):
    # A non-container can never have children; the corrupted edge is stripped
    # and the stranded subtree re-attached at the bottom of the page.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    heading = data_fixture.create_builder_heading_element(page=page)
    stranded = data_fixture.create_builder_heading_element(page=page)

    page.graph = {
        "0": heading.id,
        str(heading.id): {"children": {"": [stranded.id]}},
        str(stranded.id): {},
    }
    page.save(update_fields=["graph"])

    PageHandler().heal_corrupted_graph(page)

    page.refresh_from_db(fields=["graph"])
    assert page.graph == {
        "0": heading.id,
        str(heading.id): {"next": {"": [stranded.id]}},
        str(stranded.id): {},
    }
    assert PageHandler().heal_corrupted_graph(page) == {}


@pytest.mark.django_db
def test_corruption_prevented_place_validation_runs_after_lock(data_fixture):
    # The producer: a move into container place "2" validated against a stale
    # pre-lock read of the container row, while a concurrent transaction
    # shrank the container to two columns. Validation now runs after the page
    # lock against a fresh fetch, so the racer is rejected. Simulated
    # deterministically: the lock's side effect plays the concurrent shrink
    # that committed while this request waited on the row lock.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    column = data_fixture.create_builder_column_element(page=page, column_amount=3)
    child = data_fixture.create_builder_heading_element(page=page)

    page.refresh_from_db(fields=["graph"])
    before = dict(page.graph)

    real_lock = BaseGraphHandler._lock_instance_for_update

    def shrinking_lock(self):
        ColumnElement.objects.filter(id=column.id).update(column_amount=2)
        return real_lock(self)

    with mock_patch.object(
        BaseGraphHandler, "_lock_instance_for_update", shrinking_lock
    ):
        with pytest.raises(DRFValidationError):
            ElementService().move_element(
                user,
                page,
                ElementHandler().get_element_for_update(child.id),
                "2",
                column.id,
                GraphPointPosition.CHILD,
            )

    page.refresh_from_db(fields=["graph"])
    assert page.graph == before
    assert (
        PageHealingHandler().find_invalid_children_edge_pairs(page, page.graph) == set()
    )


# ====================================================
# -- Composites: several corruption classes at once --
# ====================================================


@pytest.mark.django_db
def test_heal_reconciles_orphan_and_stale_point_together(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    heading = element_type_registry.get("heading")
    e1 = ElementService().create_element(user, heading, page=page)
    e2 = ElementService().create_element(user, heading, page=page)

    # e2 was hard-deleted (stale), and a fresh row was written without a graph
    # insert (orphan) — both at once, as can happen mid-deploy.
    Element.objects.filter(id=e2.id).delete()
    orphan = ElementHandler().create_element(heading, page=page)

    page.refresh_from_db(fields=["graph"])
    assert str(orphan.id) not in page.graph

    PageHandler().heal_corrupted_graph(page)

    page.refresh_from_db(fields=["graph"])
    # Stale e2 pruned, orphan appended to the end of the (now single-element) chain.
    assert page.graph == {
        "0": e1.id,
        str(e1.id): {"next": {"": [orphan.id]}},
        str(orphan.id): {},
    }


@pytest.mark.django_db
def test_heal_repairs_ghost_element_with_surviving_reference(data_fixture):
    # A "ghost": the element row exists and a reference to it survives, but
    # its graph entry was lost (pre-lock stale write). This is one state, two
    # drift classes at once: the surviving reference is dangling (its target
    # is unkeyed) and the element itself is an orphan (in the DB, not keyed).
    # The write guards fail closed on moving such an element, so the heal must
    # strip the reference and re-append the element to make it usable again.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    first = data_fixture.create_builder_heading_element(page=page)
    ghost = data_fixture.create_builder_heading_element(page=page)

    page.graph = {
        "0": first.id,
        str(first.id): {"next": {"": [ghost.id]}},
    }
    page.save(update_fields=["graph"])

    PageHandler().heal_corrupted_graph(page)

    page.refresh_from_db(fields=["graph"])
    assert page.graph == {
        "0": first.id,
        str(first.id): {"next": {"": [ghost.id]}},
        str(ghost.id): {},
    }
    # The previously blocked element is movable again.
    ElementService().move_element(
        user,
        page,
        ElementHandler().get_element_for_update(ghost.id),
        "",
        first.id,
        GraphPointPosition.NORTH,
    )


@pytest.mark.django_db
def test_heal_repairs_real_world_composite_corruption(data_fixture):
    # Anonymized shape of the customer page that motivated the cycle and
    # convergence healing: a root chain (h1 -> h2 -> column -> tail) whose
    # column holds a slot chain (c1 -> c2), corrupted by
    # - a back-edge c2 -> h2 (the column's slot chain loops back onto the
    #   column's predecessor: h2 becomes doubly referenced and the column its
    #   own transitive parent), and
    # - a diamond: a stray element also references the tail.
    # One heal pass must repair everything.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    h1 = data_fixture.create_builder_heading_element(page=page)
    h2 = data_fixture.create_builder_heading_element(page=page)
    column = data_fixture.create_builder_column_element(page=page, column_amount=2)
    c1 = data_fixture.create_builder_choice_element(page=page)
    c2 = data_fixture.create_builder_choice_element(page=page)
    slot_1 = data_fixture.create_builder_heading_element(page=page)
    tail = data_fixture.create_builder_heading_element(page=page)
    stray = data_fixture.create_builder_heading_element(page=page)

    page.graph = {
        "0": h1.id,
        str(h1.id): {"next": {"": [h2.id]}},
        str(h2.id): {"next": {"": [column.id]}},
        str(column.id): {
            "next": {"": [tail.id]},
            "children": {"0": [c1.id], "1": [slot_1.id]},
        },
        str(c1.id): {"next": {"": [c2.id]}},
        str(c2.id): {"next": {"": [h2.id]}},
        str(slot_1.id): {},
        str(tail.id): {},
        str(stray.id): {"next": {"": [tail.id]}},
    }
    page.save(update_fields=["graph"])

    # The corruption makes the column its own parent.
    assert column.parent_element_id == column.id

    PageHandler().heal_corrupted_graph(page)

    page.refresh_from_db(fields=["graph"])
    assert page.graph == {
        "0": h1.id,
        str(h1.id): {"next": {"": [h2.id]}},
        str(h2.id): {"next": {"": [column.id]}},
        str(column.id): {
            "next": {"": [tail.id]},
            "children": {"0": [c1.id], "1": [slot_1.id]},
        },
        str(c1.id): {"next": {"": [c2.id]}},
        str(c2.id): {},
        str(slot_1.id): {},
        # The stray lost its surplus reference to the tail and was re-attached
        # at the bottom of the page.
        str(tail.id): {"next": {"": [stray.id]}},
        str(stray.id): {},
    }
    # Ancestry resolves sanely again.
    assert column.parent_element_id is None
    assert c2.parent_element_id == column.id
    assert PageHandler().heal_corrupted_graph(page) == {}


@pytest.mark.django_db
def test_corruption_prevented_attempted_producers_leave_graph_consistent(
    data_fixture,
):
    # Barrage test: every historical corruption producer is attempted against
    # one realistic page. Each must be rejected, and afterwards every
    # corruption detector must come back empty — no partial writes.
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    heading = data_fixture.create_builder_heading_element(page=page)
    column = data_fixture.create_builder_column_element(page=page, column_amount=2)
    child = data_fixture.create_builder_choice_element(page=page)

    page.refresh_from_db(fields=["graph"])
    page.graph[str(column.id)] = {"children": {"0": [child.id]}}
    page.graph.pop(str(child.id), None)
    page.graph[str(child.id)] = {}
    page.save(update_fields=["graph"])
    page.refresh_from_db(fields=["graph"])
    before = dict(page.graph)

    def self_move():
        ElementService().move_element(
            user,
            page,
            ElementHandler().get_element_for_update(heading.id),
            "",
            heading.id,
            GraphPointPosition.SOUTH,
        )

    def subtree_move():
        ElementService().move_element(
            user,
            page,
            ElementHandler().get_element_for_update(column.id),
            "",
            child.id,
            GraphPointPosition.SOUTH,
        )

    def double_insert():
        page.get_graph().insert(heading, column, GraphPointPosition.SOUTH, "")

    for attempt, expected_error in [
        (self_move, GraphPointReferencePointInvalid),
        (subtree_move, ElementMoveNotAllowed),
        (double_insert, GraphPointReferencePointInvalid),
    ]:
        with pytest.raises(expected_error):
            attempt()

    page.refresh_from_db(fields=["graph"])
    assert page.graph == before
    graph = page.graph
    assert BaseGraphHandler.find_self_referencing_point_ids(graph) == set()
    assert BaseGraphHandler.find_dangling_reference_ids(graph) == set()
    assert BaseGraphHandler.find_cycle_reference_pairs(graph) == set()
    assert BaseGraphHandler.find_converging_reference_pairs(graph) == set()
    assert BaseGraphHandler.find_unreachable_point_ids(graph) == set()
    assert PageHandler().heal_corrupted_graph(page) == {}


# =========================================
# -- Service wiring and Sentry reporting --
# =========================================


@pytest.mark.django_db
def test_heal_corrupted_graph_service_returns_patch_and_persists(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_fixture.create_builder_heading_element(page=page)
    orphan = ElementHandler().create_element(
        element_type_registry.get("heading"), page=page
    )

    patch = PageService().heal_corrupted_graph(user, page)

    assert str(orphan.id) in patch
    page.refresh_from_db(fields=["graph"])
    assert str(orphan.id) in page.graph


@pytest.mark.django_db
@patch("sentry_sdk.capture_message")
def test_heal_corrupted_graph_reports_to_sentry(capture_message_mock, data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_fixture.create_builder_heading_element(page=page)
    ElementHandler().create_element(element_type_registry.get("heading"), page=page)

    PageHandler().heal_corrupted_graph(page)

    capture_message_mock.assert_called_once()
    # The message reports how many elements were healed, at warning level.
    assert "1 orphan" in capture_message_mock.call_args[0][0]
    assert capture_message_mock.call_args.kwargs["level"] == "warning"


@pytest.mark.django_db
@patch("sentry_sdk.capture_message")
def test_heal_reports_pruned_stale_points_to_sentry(capture_message_mock, data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    heading = element_type_registry.get("heading")
    e1 = ElementService().create_element(user, heading, page=page)
    ElementService().create_element(user, heading, page=page)
    Element.objects.filter(id=e1.id).delete()

    PageHandler().heal_corrupted_graph(page)

    capture_message_mock.assert_called_once()
    assert "1 stale" in capture_message_mock.call_args[0][0]
    assert capture_message_mock.call_args.kwargs["level"] == "warning"


@pytest.mark.django_db
@patch("sentry_sdk.capture_message")
def test_heal_corrupted_graph_does_not_report_when_consistent(
    capture_message_mock, data_fixture
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_fixture.create_builder_heading_element(page=page)

    PageHandler().heal_corrupted_graph(page)

    capture_message_mock.assert_not_called()
