from copy import deepcopy

from baserow.core.graph.handler import BaseGraphHandler
from baserow.core.graph.types import GraphPointPosition
from tests.baserow.core.graph.fixtures import make_graph_model, make_point


def get_place_chain_ids(model, container_id, place):
    graph = model.get_graph()
    container_point = model.points[container_id]
    children = graph.get_children(container_point, output=str(place))
    if not children:
        return []
    return [p.id for p in graph._get_chain_elements(children[0].id)]


def test_merge_two_single_element_places(container_graph_fixture):
    """
    Before:  place "0" = [2], place "1" = [4]
    Merge "1" into "0"
    After:   place "0" = [2, 4], place "1" gone
    """
    model = container_graph_fixture
    graph = model.get_graph()

    graph.merge_children_into_place(model.points[1], from_places=["1"], to_place="0")

    assert get_place_chain_ids(model, 1, "0") == [2, 3, 4]
    assert get_place_chain_ids(model, 1, "1") == []
    assert get_place_chain_ids(model, 1, "2") == [5, 6]


def test_merge_two_multi_element_places():
    """
    Before:  place "0" = [A → B], place "1" = [C → D]
    Merge "1" into "0"
    After:   place "0" = [A → B → C → D], place "1" gone
    """
    model = make_graph_model(
        {
            "0": 1,
            "1": {"children": {"0": [2], "1": [4]}},
            "2": {"next": {"": [3]}},
            "3": {},
            "4": {"next": {"": [5]}},
            "5": {},
        }
    )
    graph = model.get_graph()

    graph.merge_children_into_place(model.points[1], from_places=["1"], to_place="0")

    assert get_place_chain_ids(model, 1, "0") == [2, 3, 4, 5]
    assert get_place_chain_ids(model, 1, "1") == []


def test_merge_middle_place_into_lower(container_graph_fixture):
    """
    Before:  place "0" = [2 → 3], place "1" = [4], place "2" = [5 → 6]
    Merge "2" into "1"  (rightmost column removed, target is column 1)
    After:   place "0" unchanged, place "1" = [4, 5, 6], place "2" gone
    """
    model = container_graph_fixture
    graph = model.get_graph()

    graph.merge_children_into_place(model.points[1], from_places=["2"], to_place="1")

    assert get_place_chain_ids(model, 1, "0") == [2, 3]
    assert get_place_chain_ids(model, 1, "1") == [4, 5, 6]
    assert get_place_chain_ids(model, 1, "2") == []


def test_merge_multiple_places_at_once(container_graph_fixture):
    """
    Before:  place "0" = [2 → 3], place "1" = [4], place "2" = [5 → 6]
    Merge ["1", "2"] into "0"
    After:   place "0" = [2, 3, 4, 5, 6], places "1" and "2" gone
    """
    model = container_graph_fixture
    graph = model.get_graph()

    graph.merge_children_into_place(
        model.points[1], from_places=["1", "2"], to_place="0"
    )

    assert get_place_chain_ids(model, 1, "0") == [2, 3, 4, 5, 6]
    assert get_place_chain_ids(model, 1, "1") == []
    assert get_place_chain_ids(model, 1, "2") == []


def test_merge_into_empty_place():
    """
    Before:  place "0" = [], place "1" = [A → B]
    Merge "1" into "0"
    After:   place "0" = [A → B], place "1" gone
    """
    model = make_graph_model(
        {
            "0": 1,
            "1": {"children": {"1": [2]}},
            "2": {"next": {"": [3]}},
            "3": {},
        }
    )
    graph = model.get_graph()

    graph.merge_children_into_place(model.points[1], from_places=["1"], to_place="0")

    assert get_place_chain_ids(model, 1, "0") == [2, 3]
    assert get_place_chain_ids(model, 1, "1") == []


def test_merge_from_empty_place_is_noop(container_graph_fixture):
    """
    Merging from a non-existent place leaves the graph unchanged.
    """
    model = container_graph_fixture
    graph = model.get_graph()

    moved = graph.merge_children_into_place(
        model.points[1], from_places=["9"], to_place="0"
    )

    assert moved == []
    assert get_place_chain_ids(model, 1, "0") == [2, 3]
    assert get_place_chain_ids(model, 1, "1") == [4]
    assert get_place_chain_ids(model, 1, "2") == [5, 6]


def test_get_siblings_returns_empty_for_lone_child(container_graph_fixture):
    model = container_graph_fixture
    graph = model.get_graph()
    assert graph.get_siblings(model.points[4]) == []


def test_get_siblings_returns_all_siblings_in_chain(container_graph_fixture):
    model = container_graph_fixture
    graph = model.get_graph()
    assert [p.id for p in graph.get_siblings(model.points[2])] == [3]
    assert [p.id for p in graph.get_siblings(model.points[3])] == [2]
    assert [p.id for p in graph.get_siblings(model.points[5])] == [6]
    assert [p.id for p in graph.get_siblings(model.points[6])] == [5]


def test_remove_permutations():
    """
    Removing a point with no children, one child, and multiple chained children.
    In all cases the return value must contain point_removed and dependencies_removed.
    """

    # ── Case 1: remove a point with no children ───────────────────────────────
    # Graph: root -> p1 -> p2
    model = make_graph_model({"0": 1, "1": {"next": {"": [2]}}, "2": {}})
    p1, p2 = model.points[1], model.points[2]
    graph = model.get_graph()

    result = graph.remove(p1)

    assert result.point_removed is p1
    assert result.dependencies_removed == []
    # p2 is promoted to root; p1's info is gone
    assert model.graph["0"] == 2
    assert "1" not in model.graph

    # ── Case 2: remove a point that has exactly one child ─────────────────────
    # Graph: root -> p1 (children: {"0": [p2]})
    model = make_graph_model({"0": 1, "1": {"children": {"0": [2]}}, "2": {}})
    p1, p2 = model.points[1], model.points[2]
    graph = model.get_graph()

    result = graph.remove(p1)

    assert result.point_removed is p1
    assert [p.id for p in result.dependencies_removed] == [2]
    # Both p1 and its child p2 are gone; graph is empty
    assert model.graph == {}

    # ── Case 3: remove a point whose child slot contains a next chain ─────────
    # Graph: root -> p1 (children: {"0": [p2]}), p2 -> p3 -> p4
    model = make_graph_model(
        {
            "0": 1,
            "1": {"children": {"0": [2]}},
            "2": {"next": {"": [3]}},
            "3": {"next": {"": [4]}},
            "4": {},
        }
    )
    p1, p2, p3, p4 = (model.points[i] for i in [1, 2, 3, 4])
    graph = model.get_graph()

    result = graph.remove(p1)

    assert result.point_removed is p1
    assert [p.id for p in result.dependencies_removed] == [2, 3, 4]
    assert model.graph == {}


def test_insert_child_with_none_output_uses_default_edge():
    # Regression: a child insert with output=None (e.g. a move carrying a null
    # place_in_container) must land in the default "" slot — never a bogus "None"
    # slot key, since str(None) == "None".
    model = make_graph_model({"0": 1, "1": {}})
    graph = model.get_graph()

    child = make_point(2, model)
    graph.insert(child, model.points[1], "child", output=None)

    assert model.graph["1"]["children"] == {"": [2]}
    assert "None" not in model.graph["1"]["children"]


def test_insert_permutations():
    model = make_graph_model({})
    graph = model.get_graph()

    # Insert into empty graph — becomes root at key "0"
    p1 = make_point(1, model)
    graph.insert(p1, None, "south", output="")
    assert model.graph["0"] == 1

    # Insert south of root — chains via next[""]
    p2 = make_point(2, model)
    graph.insert(p2, p1, "south", output="")
    assert model.graph["1"]["next"][""] == [2]

    # Insert north of p2 — takes p2's position, p2 becomes its next
    p3 = make_point(3, model)
    graph.insert(p3, p2, "north", output="")
    assert model.graph["1"]["next"][""] == [3]
    assert model.graph["3"]["next"][""] == [2]

    # Insert child of p2 in place "0" — first child goes into children
    p4 = make_point(4, model)
    graph.insert(p4, p2, "child", output="0")
    assert model.graph["2"]["children"]["0"] == [4]

    # Insert another child of p2 in same place "0" — the new child becomes the
    # head of the slot and the previous head (p4) becomes its next. This mirrors
    # get_position (which reports "child" only for the head child) and the
    # frontend's _insertAt, so move undo/redo round-trips for a head child.
    p5 = make_point(5, model)
    graph.insert(p5, p2, "child", output="0")
    assert model.graph["2"]["children"]["0"] == [5]
    assert model.graph["5"]["next"][""] == [4]

    # Insert into graph with existing root (None ref) — new point becomes
    # root, old root (p1) becomes its next.
    # Graph before: 0 -> p1 -> p3 -> p2 (with children p4 -> p5)
    p6 = make_point(6, model)
    graph.insert(p6, None, "south", output="")
    assert model.graph["0"] == 6
    assert model.graph["6"]["next"][""] == [1]

    # Insert north of root — new point replaces root, old root becomes next.
    # Graph before: 0 -> p6 -> p1 -> ...
    p7 = make_point(7, model)
    graph.insert(p7, p6, "north", output="")
    assert model.graph["0"] == 7
    assert model.graph["7"]["next"][""] == [6]

    # Insert south of p3 which already has next (p2) — new point takes p2's
    # spot, p2 becomes the new point's next.
    # Chain before: p3 -> p2
    p8 = make_point(8, model)
    graph.insert(p8, p3, "south", output="")
    assert model.graph["3"]["next"][""] == [8]
    assert model.graph["8"]["next"][""] == [2]

    # Insert north of p5 which is now the child head — new point replaces p5 in
    # children dict, p5 becomes new point's next.
    p9 = make_point(9, model)
    graph.insert(p9, p5, "north", output="")
    assert model.graph["2"]["children"]["0"] == [9]
    assert model.graph["9"]["next"][""] == [5]


def test_append_permutations():
    model = make_graph_model({})
    graph = model.get_graph()

    # Append to empty graph — becomes root at key "0"
    p1 = make_point(1, model)
    graph.append(p1)
    assert model.graph["0"] == 1
    assert model.graph["1"] == {}

    # Append a second point — chains south of p1 via next[""]
    p2 = make_point(2, model)
    graph.append(p2)
    assert model.graph["1"]["next"][""] == [2]

    # Append a third point — chains south of p2, tail of the default edge
    p3 = make_point(3, model)
    graph.append(p3)
    assert model.graph["2"]["next"][""] == [3]
    assert model.graph["3"] == {}


def test_build_previous_position_map_nested_graph():
    graph = {
        "0": 1,
        "1": {"children": {"outer": [2, 6]}},
        "2": {"children": {"inner": [3]}},
        "3": {"next": {"": [4], "branch": [5]}},
        "4": {},
        "5": {},
    }

    assert BaseGraphHandler.build_previous_position_map(graph) == {
        1: (None, GraphPointPosition.SOUTH, ""),
        2: (1, GraphPointPosition.CHILD, "outer"),
        3: (2, GraphPointPosition.CHILD, "inner"),
        4: (3, GraphPointPosition.SOUTH, ""),
        5: (3, GraphPointPosition.SOUTH, "branch"),
    }


def test_get_children_permutations():
    model = make_graph_model({})
    graph = model.get_graph()

    # Empty graph — no point has children
    p1 = make_point(1, model)
    graph.insert(p1, None, "south", output="")
    assert graph.get_children(p1) == []

    # Flat chain only — siblings are not children
    p2 = make_point(2, model)
    graph.insert(p2, p1, "south", output="")
    p3 = make_point(3, model)
    graph.insert(p3, p2, "south", output="")
    assert graph.get_children(p1) == []

    # Single child in place "0" — first_only=False returns the same as first_only=True
    p4 = make_point(4, model)
    graph.insert(p4, p1, "child", output="0")
    assert graph.get_children(p1) == [p4]
    assert graph.get_children(p1, first_only=True) == [p4]
    assert graph.get_children(p1, output="0") == [p4]
    assert graph.get_children(p1, output="1") == []  # wrong slot

    # Insert p5 as a child of p1 in slot "0" — it prepends as the new head, so
    # the slot chain becomes p5 -> p4. first_only=False follows the chain.
    p5 = make_point(5, model)
    graph.insert(p5, p1, "child", output="0")
    assert graph.get_children(p1, first_only=False) == [p5, p4]
    assert graph.get_children(p1, first_only=True) == [p5]  # only entry-point
    assert graph.get_children(p1, output="0", first_only=False) == [p5, p4]
    assert graph.get_children(p1, output="0", first_only=True) == [p5]

    # Second slot "1" with its own child p6
    p6 = make_point(6, model)
    graph.insert(p6, p1, "child", output="1")
    # No output filter — both slots included
    assert graph.get_children(p1, first_only=False) == [p5, p4, p6]
    assert graph.get_children(p1, first_only=True) == [p5, p6]
    # Per-slot filtering still works
    assert graph.get_children(p1, output="0", first_only=False) == [p5, p4]
    assert graph.get_children(p1, output="1") == [p6]

    # Nested container: p4 has its own child p7 — get_children(p1) does NOT descend
    p7 = make_point(7, model)
    graph.insert(p7, p4, "child", output="")
    assert graph.get_children(p4) == [p7]
    assert p7 not in graph.get_children(p1)  # children of p1 don't include p7


def test_move_with_same_target_graph_is_equivalent_to_plain_move():
    """
    Passing target_graph=self is equivalent to a plain move().
    """

    model = make_graph_model({})
    graph = model.get_graph()

    p1 = make_point(1, model)
    p2 = make_point(2, model)
    p3 = make_point(3, model)
    graph.insert(p1, None, "south")
    graph.insert(p2, p1, "south")
    graph.insert(p3, p2, "south")
    # Chain: root → p1 → p2 → p3

    graph.move(p1, p3, "south", target_graph=graph)

    # root → p2 → p3 → p1
    assert model.graph["0"] == 2
    assert model.graph["2"]["next"][""] == [3]
    assert model.graph["3"]["next"][""] == [1]


def test_move_with_target_graph_removes_from_source_inserts_into_target():
    """
    Cross-graph move: point leaves the source graph and appears in the target graph.

    move() uses remove(keep_info=True) so the source entry — including any
    children info — is preserved for post-move traversal by after_move hooks.
    Callers are responsible for calling remove_isolated_point() once those
    hooks have finished.
    """

    source_model = make_graph_model({})
    source_graph = source_model.get_graph()
    target_model = make_graph_model({})
    target_graph = target_model.get_graph()

    p1 = make_point(1, source_model)
    p2 = make_point(2, source_model)
    p3 = make_point(3, source_model)

    # Source: root → p1 → p2; p1 has child p3 in slot "0"
    source_graph.insert(p1, None, "south")
    source_graph.insert(p2, p1, "south")
    source_graph.insert(p3, p1, "child", output="0")

    source_graph.move(p1, None, "south", target_graph=target_graph)

    # After move(): p2 is root; p1's entry is deliberately preserved (with its
    # children dict) so that callers can traverse it during after_move hooks.
    assert source_model.graph["0"] == 2
    assert "1" in source_model.graph
    assert source_model.graph["1"]["children"]["0"] == [3]

    # Target: p1 is at the root
    assert target_model.graph["0"] == 1


def test_remove_isolated_point_cleans_up_cross_graph_move_stale_entries():
    """
    After a cross-graph move, remove_isolated_point() removes the moved
    point's stale entry (and any descendants) from the source graph so that
    no orphaned nodes are left behind.
    """

    source_model = make_graph_model({})
    source_graph = source_model.get_graph()
    target_model = make_graph_model({})
    target_graph = target_model.get_graph()

    p1 = make_point(1, source_model)
    p2 = make_point(2, source_model)
    p3 = make_point(3, source_model)

    # Source: root → p1 → p2; p1 has child p3 in slot "0"
    source_graph.insert(p1, None, "south")
    source_graph.insert(p2, p1, "south")
    source_graph.insert(p3, p1, "child", output="0")

    source_graph.move(p1, None, "south", target_graph=target_graph)
    # Simulate the service calling remove_isolated_point after after_move hooks.
    source_graph.remove_isolated_point(p1)

    # Source: p1 and its child p3 are both gone; only p2 remains.
    assert source_model.graph["0"] == 2
    assert "1" not in source_model.graph
    assert "3" not in source_model.graph
    assert str(p2.id) in source_model.graph

    # Target graph is unchanged.
    assert target_model.graph["0"] == 1


def test_get_descendants_returns_full_subtree():
    """
    get_descendants returns all direct and transitive children of a point.
    """

    model = make_graph_model(
        {
            "0": 1,
            "1": {"children": {"": [2]}},
            "2": {"next": {"": [3]}, "children": {"": [4]}},
            "3": {},
            "4": {},
        }
    )
    graph = model.get_graph()

    descendants = graph.get_descendants(model.points[1])

    assert sorted(p.id for p in descendants) == [2, 3, 4]
    # A leaf point has no descendants.
    assert graph.get_descendants(model.points[4]) == []


def test_cross_graph_move_migrates_subtree_not_siblings():
    """
    A cross-graph move must carry the moved point's whole subtree (its children
    and their descendants) into the target graph, but NOT its old siblings (its
    `next`), which stay behind in the source graph.
    """

    source_model = make_graph_model({})
    source_graph = source_model.get_graph()
    target_model = make_graph_model({})
    target_graph = target_model.get_graph()

    p1 = make_point(1, source_model)  # container
    p2 = make_point(2, source_model)  # child of the container
    p3 = make_point(3, source_model)  # sibling after the container (stays behind)

    # Source: root → p1 → p3 ; p1 has child p2.
    source_graph.insert(p1, None, "south")
    source_graph.insert(p3, p1, "south")
    source_graph.insert(p2, p1, "child", output="")

    source_graph.move(p1, None, "south", target_graph=target_graph)

    # The container AND its child reached the target graph.
    assert target_model.graph["0"] == 1
    assert target_model.graph["1"]["children"][""] == [2]
    assert "2" in target_model.graph
    # The sibling did NOT travel; the root's old `next` was not carried over.
    assert "3" not in target_model.graph
    assert target_model.graph["1"].get("next", {}).get("", []) == []

    # The sibling was relinked as the new source root.
    assert source_model.graph["0"] == 3


# ---------------------------------------------------------------------------
# prune_points: removing "stale" points (referenced in the graph but whose DB
# row is gone, e.g. hard-deleted by old code during a non-zero-downtime deploy).
# ---------------------------------------------------------------------------


def test_prune_points_splices_out_a_middle_point():
    # 1 → 2 → 3, point 2 is stale.
    model = make_graph_model(
        {
            "0": 1,
            "1": {"next": {"": [2]}},
            "2": {"next": {"": [3]}},
            "3": {},
        }
    )
    graph = model.get_graph()

    assert graph.prune_points([2]) == [2]

    # 2 is gone and 1 now links straight to 3.
    assert model.graph == {
        "0": 1,
        "1": {"next": {"": [3]}},
        "3": {},
    }


def test_prune_points_removes_a_tail_point():
    model = make_graph_model(
        {
            "0": 1,
            "1": {"next": {"": [2]}},
            "2": {},
        }
    )
    graph = model.get_graph()

    assert graph.prune_points([2]) == [2]

    # 1 keeps no dangling empty next dict.
    assert model.graph == {"0": 1, "1": {}}


def test_prune_points_promotes_successor_when_root_is_stale():
    model = make_graph_model(
        {
            "0": 1,
            "1": {"next": {"": [2]}},
            "2": {"next": {"": [3]}},
            "3": {},
        }
    )
    graph = model.get_graph()

    assert graph.prune_points([1]) == [1]

    # The old root (1) is gone; its successor (2) becomes the new root.
    assert model.graph == {
        "0": 2,
        "2": {"next": {"": [3]}},
        "3": {},
    }


def test_prune_points_empties_graph_when_only_point_is_stale():
    model = make_graph_model({"0": 1, "1": {}})
    graph = model.get_graph()

    assert graph.prune_points([1]) == [1]

    assert model.graph == {}


def test_prune_points_removes_stale_child_head_keeping_siblings():
    # Container 1 holds, in place "0": 2 → 3. The head child 2 is stale.
    model = make_graph_model(
        {
            "0": 1,
            "1": {"children": {"0": [2]}},
            "2": {"next": {"": [3]}},
            "3": {},
        }
    )
    graph = model.get_graph()

    assert graph.prune_points([2]) == [2]

    # 3 becomes the head of place "0".
    assert model.graph == {
        "0": 1,
        "1": {"children": {"0": [3]}},
        "3": {},
    }


def test_prune_points_drops_cascaded_stale_subtree():
    # Container 2 (a child of root 1) is stale along with its whole subtree
    # (children 4, 5) — mimicking an old-code cascade delete that left the
    # subtree dangling in the graph. 2's sibling-successor 3 must survive.
    model = make_graph_model(
        {
            "0": 1,
            "1": {"next": {"": [2]}},
            "2": {"next": {"": [3]}, "children": {"0": [4]}},
            "3": {},
            "4": {"next": {"": [5]}},
            "5": {},
        }
    )
    graph = model.get_graph()

    pruned = graph.prune_points([2, 4, 5])

    assert set(pruned) == {2, 4, 5}
    # 1 links straight to 3; the whole stale subtree is gone.
    assert model.graph == {
        "0": 1,
        "1": {"next": {"": [3]}},
        "3": {},
    }


def test_prune_points_is_order_independent():
    # Same cascade as above but the ids are given children-first.
    model = make_graph_model(
        {
            "0": 1,
            "1": {"next": {"": [2]}},
            "2": {"next": {"": [3]}, "children": {"0": [4]}},
            "3": {},
            "4": {"next": {"": [5]}},
            "5": {},
        }
    )
    graph = model.get_graph()

    pruned = graph.prune_points([5, 4, 2])

    assert set(pruned) == {2, 4, 5}
    assert model.graph == {
        "0": 1,
        "1": {"next": {"": [3]}},
        "3": {},
    }


def test_prune_points_ignores_unknown_ids():
    model = make_graph_model({"0": 1, "1": {"next": {"": [2]}}, "2": {}})
    graph = model.get_graph()

    assert graph.prune_points([999]) == []
    assert model.graph == {"0": 1, "1": {"next": {"": [2]}}, "2": {}}


def test_get_position_of_root_is_north():
    # The root must report `(None, "north", "")` so the triplet round-trips back
    # through move()/insert() (which restore the root) rather than colliding with
    # `(None, "south")`, which move() treats as "append to the end".
    model = make_graph_model({})
    graph = model.get_graph()
    p1 = make_point(1, model)
    graph.insert(p1, None, "south")

    assert graph.get_position(p1) == (None, GraphPointPosition.NORTH, "")


def test_move_root_point_then_restore_via_captured_position():
    # Reproduces the undo bug: moving the first (root) point away and then
    # restoring it to its captured position must put it back at the root, not at
    # the end of the chain.
    model = make_graph_model({})
    graph = model.get_graph()
    p1 = make_point(1, model)
    p2 = make_point(2, model)
    p3 = make_point(3, model)
    graph.insert(p1, None, "south")
    graph.insert(p2, p1, "south")
    graph.insert(p3, p2, "south")
    # 0 -> 1 -> 2 -> 3, with p1 at the root.

    # Capture the root's position (as an undo would).
    previous_position = graph.get_position(p1)
    assert previous_position == (None, GraphPointPosition.NORTH, "")

    # Move p1 to just before the last point: 0 -> 2 -> 1 -> 3.
    graph.move(p1, p3, "north")
    assert model.graph["0"] == 2
    assert model.graph["2"]["next"][""] == [1]
    assert model.graph["1"]["next"][""] == [3]

    # Undo: move p1 back to its captured (root) position.
    ref_id, position, output = previous_position
    reference = graph.get_point(ref_id) if ref_id is not None else None
    graph.move(p1, reference, position, output)

    # p1 is the root again and the original chain is fully restored.
    assert model.graph["0"] == 1
    assert model.graph["1"]["next"][""] == [2]
    assert model.graph["2"]["next"][""] == [3]
    assert "next" not in model.graph["3"]


def test_replace_root_point():
    # `replace` must update the root key when the replaced point is the root,
    # regardless of the position reported by get_position.
    model = make_graph_model({})
    graph = model.get_graph()
    p1 = make_point(1, model)
    p2 = make_point(2, model)
    graph.insert(p1, None, "south")
    graph.insert(p2, p1, "south")
    # 0 -> 1 -> 2.

    p3 = make_point(3, model)
    graph.replace(p1, p3)

    assert model.graph["0"] == 3
    assert "1" not in model.graph
    assert model.graph["3"]["next"][""] == [2]


def test_remove_container_when_child_point_is_missing_from_point_map():
    # A graph entry can reference a point whose model instance no longer exists
    # (e.g. a record hard-deleted outside the graph). Removing the parent must
    # not raise: the stale entry is cleaned out of the graph, and only the
    # points that still exist are returned as dependencies_removed.
    model = make_graph_model(
        {
            "0": 1,
            "1": {"children": {"": [2]}, "next": {"": [5]}},
            "2": {"next": {"": [3]}},
            "3": {"next": {"": [4]}},
            "4": {},
            "5": {},
        }
    )
    del model.points[3]
    graph = model.get_graph()

    result = graph.remove(model.points[1])

    assert result.point_removed is model.points[1]
    assert [p.id for p in result.dependencies_removed] == [2, 4]
    # All descendant entries — including the stale one — are gone, and the
    # removed root is replaced by its successor.
    assert model.graph == {"0": 5, "5": {}}


def test_remove_container_with_self_referencing_child():
    # Regression: a corrupted graph in which a container's child has itself as
    # `next` used to make removing the container loop forever. The traversal
    # must detect the already-seen point, heal the duplicate reference, and
    # complete the removal.
    model = make_graph_model(
        {
            "0": 3,
            "3": {"next": {"": [1]}},
            "1": {"children": {"": [2]}, "next": {"": [4]}},
            "2": {"next": {"": [2]}},
            "4": {},
        }
    )
    graph = model.get_graph()

    result = graph.remove(model.points[1])

    assert [p.id for p in result.dependencies_removed] == [2]
    assert model.graph == {"0": 3, "3": {"next": {"": [4]}}, "4": {}}


def test_remove_point_whose_next_is_itself():
    # Removing the self-referencing point directly must not splice the removed
    # point back in as its own successor.
    model = make_graph_model(
        {"0": 1, "1": {"children": {"": [2]}}, "2": {"next": {"": [2]}}}
    )
    graph = model.get_graph()

    graph.remove(model.points[2])

    assert model.graph == {"0": 1, "1": {}}


def test_get_children_heals_self_referencing_next():
    # Traversing a chain must track the points already seen; a `next` pointing
    # back at an already-seen point is removed and the graph is collapsed.
    model = make_graph_model(
        {"0": 1, "1": {"children": {"": [2]}}, "2": {"next": {"": [2]}}}
    )
    graph = model.get_graph()

    children = graph.get_children(model.points[1])

    assert [p.id for p in children] == [2]
    # The duplicate self-reference has been healed away and persisted.
    assert model.graph["2"] == {}


def test_get_children_heals_chain_looping_back_to_earlier_point():
    # A longer cycle: 2 -> 3 -> 2. The traversal returns each point once and
    # removes the reference that closes the loop.
    model = make_graph_model(
        {
            "0": 1,
            "1": {"children": {"": [2]}},
            "2": {"next": {"": [3]}},
            "3": {"next": {"": [2]}},
        }
    )
    graph = model.get_graph()

    children = graph.get_children(model.points[1])

    assert [p.id for p in children] == [2, 3]
    assert model.graph["2"] == {"next": {"": [3]}}
    assert model.graph["3"] == {}


def test_get_last_position_terminates_on_looping_root_chain():
    # 1 -> 2 -> 1: following the default edge from the root must terminate and
    # heal the reference that closes the loop.
    model = make_graph_model(
        {"0": 1, "1": {"next": {"": [2]}}, "2": {"next": {"": [1]}}}
    )
    graph = model.get_graph()

    reference_point, position, output = graph.get_last_position()

    assert reference_point.id == 2
    assert (position, output) == ("south", "")
    assert model.graph["2"] == {}


def test_get_previous_positions_terminates_when_point_is_its_own_predecessor():
    # In this corrupted graph the previous-position map ends up recording point
    # 2 as its own predecessor (its self-referencing `next` overwrites the
    # legitimate entry). Walking the ancestry must stop instead of looping.
    model = make_graph_model(
        {"0": 1, "1": {"next": {"": [2]}}, "2": {"next": {"": [2]}}}
    )
    graph = model.get_graph()

    positions = graph.get_previous_positions(model.points[2])

    assert isinstance(positions, list)


def test_collect_all_descendants_skips_missing_points_and_terminates_on_loop():
    # Both fixes at once: a subtree containing a stale id (no model instance)
    # and a self-referencing point must still be collectable.
    model = make_graph_model(
        {
            "0": 1,
            "1": {"children": {"": [2]}},
            "2": {"next": {"": [3]}, "children": {"": [4]}},
            "3": {"next": {"": [3]}},
            "4": {},
        }
    )
    del model.points[4]
    graph = model.get_graph()

    descendants = graph.collect_all_descendants(model.points[1])

    assert [p.id for p in descendants] == [2, 3]
    # The self-loop on 3 has been healed.
    assert model.graph["3"] == {}


def test_remove_container_of_self_referencing_point_in_real_world_graph():
    # Real-world corrupted graph reported by a customer: point 3308 has itself
    # as `next`, which made deleting its container (3314) either loop forever
    # or raise when 3308's record was missing. Both variants must succeed and
    # splice 3313 straight onto 3304.
    corrupted_graph = {
        "0": 3292,
        "3292": {"next": {"": [3293]}},
        "3293": {"next": {"": [3298]}},
        "3294": {"children": {"": [3295]}},
        "3295": {"children": {"0": [3309], "1": [3310], "2": [3313], "3": [3312]}},
        "3296": {"next": {"": [3306]}},
        "3297": {"next": {"": [3302]}},
        "3298": {"next": {"": [3294]}},
        "3299": {"next": {"": [3300]}},
        "3300": {"children": {"": [3301]}},
        "3301": {},
        "3302": {"children": {"": [3303]}},
        "3303": {},
        "3304": {"children": {"": [3305]}},
        "3305": {},
        "3306": {"children": {"": [3307]}},
        "3307": {},
        "3308": {"next": {"": [3308]}},
        "3309": {"next": {"": [3299]}},
        "3310": {"next": {"": [3297]}},
        "3311": {},
        "3312": {"next": {"": [3296]}},
        "3313": {"next": {"": [3314]}},
        "3314": {"next": {"": [3304]}, "children": {"": [3308]}},
    }

    for missing_from_point_map in (False, True):
        model = make_graph_model(deepcopy(corrupted_graph))
        if missing_from_point_map:
            del model.points[3308]
        graph = model.get_graph()

        result = graph.remove(model.points[3314])

        expected_dependencies = [] if missing_from_point_map else [3308]
        assert [p.id for p in result.dependencies_removed] == expected_dependencies
        assert "3314" not in model.graph
        assert "3308" not in model.graph
        assert model.graph["3313"] == {"next": {"": [3304]}}


def test_point_whose_children_contains_itself():
    # The `children` variant of the self-reference corruption: the container
    # lists itself as its own child. Traversal must skip it, and both the
    # point itself and (in the nested variant below) its parent stay deletable.
    model = make_graph_model(
        {"0": 1, "1": {"children": {"": [1]}, "next": {"": [2]}}, "2": {}}
    )
    graph = model.get_graph()

    assert graph.get_children(model.points[1]) == []
    assert graph.collect_all_descendants(model.points[1]) == []

    graph.remove(model.points[1])
    assert model.graph == {"0": 2, "2": {}}


def test_remove_parent_of_point_whose_children_contains_itself():
    # Deleting the parent of a self-childed point must cascade cleanly.
    model = make_graph_model(
        {"0": 1, "1": {"children": {"": [2]}}, "2": {"children": {"": [2]}}}
    )
    graph = model.get_graph()

    result = graph.remove(model.points[1])

    assert [p.id for p in result.dependencies_removed] == [2]
    assert model.graph == {}


def test_prune_points_handles_self_referencing_stale_point():
    # prune_points is the heal_orphan_elements path for graph entries whose DB
    # row is gone. A stale point whose `next` is itself must not be reported as
    # its own predecessor (leaving the real parent's children dangling), nor be
    # spliced back in as its own successor.
    model = make_graph_model(
        {
            "0": 1,
            "1": {"children": {"": [2]}, "next": {"": [3]}},
            "2": {"next": {"": [2]}},
            "3": {},
        }
    )
    del model.points[2]
    graph = model.get_graph()

    removed = graph.prune_points([2])

    assert removed == [2]
    assert model.graph == {"0": 1, "1": {"next": {"": [3]}}, "3": {}}


def test_prune_points_handles_self_referencing_stale_root():
    model = make_graph_model({"0": 1, "1": {"next": {"": [1]}}})
    del model.points[1]
    graph = model.get_graph()

    removed = graph.prune_points([1])

    assert removed == [1]
    assert model.graph == {}


def test_previous_position_map_ignores_self_references():
    # Regression: with a self-referencing `next`, the map entry for the point
    # depended on dict order — the self-reference could shadow the real parent,
    # making every ancestry walk (e.g. parent_element_id on page load) loop
    # forever. Self-references must never be recorded as positions.
    graph = {
        "0": 1,
        "1": {"next": {"": [2]}},
        # The corrupted entry comes AFTER the legitimate parent (3) below, so
        # without the guard it would win as last writer.
        "3": {"children": {"": [2]}},
        "2": {"next": {"": [2]}},
    }

    position_map = BaseGraphHandler.build_previous_position_map(graph)

    assert position_map[2] == (3, GraphPointPosition.CHILD, "")

    # Same for a self-referencing child head.
    graph = {"0": 1, "1": {"next": {"": [2]}}, "2": {"children": {"": [2]}}}
    position_map = BaseGraphHandler.build_previous_position_map(graph)
    assert position_map[2] == (1, GraphPointPosition.SOUTH, "")


def test_find_self_referencing_point_ids():
    graph = {
        "0": 1,
        "1": {"children": {"": [2]}},
        "2": {"next": {"": [2]}},
        "3": {"children": {"0": [3], "1": [4]}},
        "4": {"next": {"": [1], "uuid1": [4]}},
        "5": {"children": [5]},
        "6": {"next": {"": [1]}},
    }

    assert BaseGraphHandler.find_self_referencing_point_ids(graph) == {2, 3, 4, 5}
    assert BaseGraphHandler.find_self_referencing_point_ids({}) == set()
    assert BaseGraphHandler.find_self_referencing_point_ids(None) == set()


def test_strip_self_references():
    model = make_graph_model(
        {
            "0": 1,
            "1": {"children": {"": [2]}, "next": {"": [6]}},
            "2": {"next": {"": [2]}},
            "3": {"children": {"0": [3], "1": [4]}},
            "4": {"next": {"": [1], "uuid1": [4]}},
            "6": {},
        }
    )
    graph = model.get_graph()

    stripped = graph.strip_self_references()

    assert stripped == [2, 3, 4]
    assert model.graph == {
        "0": 1,
        "1": {"children": {"": [2]}, "next": {"": [6]}},
        "2": {},
        "3": {"children": {"1": [4]}},
        "4": {"next": {"": [1]}},
        "6": {},
    }
    # Already-clean graph: nothing stripped, nothing changed.
    assert graph.strip_self_references() == []


def test_find_unreachable_point_ids():
    graph = {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {"children": {"0": [3]}},
        "3": {},
        # Detached chain: 4 -> 5, nothing references 4.
        "4": {"next": {"": [5]}},
        "5": {},
        # Detached lone point.
        "6": {},
        # Detached cycle: 7 <-> 8.
        "7": {"next": {"": [8]}},
        "8": {"next": {"": [7]}},
    }

    assert BaseGraphHandler.find_unreachable_point_ids(graph) == {4, 5, 6, 7, 8}
    assert BaseGraphHandler.find_unreachable_point_ids({"0": 1, "1": {}}) == set()
    assert BaseGraphHandler.find_unreachable_point_ids({}) == set()
    assert BaseGraphHandler.find_unreachable_point_ids(None) == set()


def test_reattach_unreachable_points_appends_at_bottom():
    # 3311-style ghost: keyed in the graph, has a model instance, but nothing
    # references it. It must become the last point of the root chain.
    model = make_graph_model({"0": 1, "1": {"next": {"": [2]}}, "2": {}, "3": {}})
    graph = model.get_graph()

    reattached = graph.reattach_unreachable_points()

    assert reattached == [3]
    assert model.graph == {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {"next": {"": [3]}},
        "3": {},
    }
    # Second call is a no-op.
    assert graph.reattach_unreachable_points() == []


def test_reattach_unreachable_points_preserves_subtree():
    # Only the head of a detached subtree is linked; its chain and children
    # ride along untouched.
    model = make_graph_model(
        {
            "0": 1,
            "1": {},
            "4": {"next": {"": [5]}, "children": {"": [6]}},
            "5": {},
            "6": {},
        }
    )
    graph = model.get_graph()

    reattached = graph.reattach_unreachable_points()

    assert reattached == [4]
    assert model.graph == {
        "0": 1,
        "1": {"next": {"": [4]}},
        "4": {"next": {"": [5]}, "children": {"": [6]}},
        "5": {},
        "6": {},
    }


def test_reattach_unreachable_points_into_empty_graph_becomes_root():
    model = make_graph_model({"1": {}})
    graph = model.get_graph()

    assert graph.reattach_unreachable_points() == [1]
    assert model.graph == {"0": 1, "1": {}}


def test_reattach_unreachable_points_into_container_slot():
    # Shared-page style: attach at the end of the container's default slot.
    model = make_graph_model({"0": 1, "1": {"children": {"": [2]}}, "2": {}, "3": {}})
    graph = model.get_graph()

    reattached = graph.reattach_unreachable_points(container=model.points[1])

    assert reattached == [3]
    assert model.graph == {
        "0": 1,
        "1": {"children": {"": [2]}},
        "2": {"next": {"": [3]}},
        "3": {},
    }


def test_reattach_unreachable_points_breaks_detached_cycle():
    # A fully cyclic detached component has no head; the cycle is broken at
    # the lowest id, which is then re-attached with the rest as its chain.
    model = make_graph_model(
        {"0": 1, "1": {}, "7": {"next": {"": [8]}}, "8": {"next": {"": [7]}}}
    )
    graph = model.get_graph()

    reattached = graph.reattach_unreachable_points()

    assert reattached == [7]
    assert model.graph == {
        "0": 1,
        "1": {"next": {"": [7]}},
        "7": {"next": {"": [8]}},
        "8": {},
    }
