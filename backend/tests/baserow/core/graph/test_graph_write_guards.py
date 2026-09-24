"""
Invariant guards at the graph write chokepoint. These scenarios used to
silently corrupt the graph (they are the reproduced root causes of the
self-referencing-point and ghost-point customer corruptions); they must now
raise so the surrounding transaction rolls back.
"""

import pytest

from baserow.core.graph.exceptions import GraphPointReferencePointInvalid
from tests.baserow.core.graph.fixtures import make_graph_model, make_point


def test_move_relative_to_itself_is_rejected():
    # Used to produce the exact "ghost" corruption: the point spliced out of
    # its position, left keyed as {} with no incoming reference.
    model = make_graph_model({"0": 1, "1": {"next": {"": [2]}}, "2": {}})
    graph = model.get_graph()

    with pytest.raises(GraphPointReferencePointInvalid):
        graph.move(model.points[2], model.points[2], "south")

    assert model.graph == {"0": 1, "1": {"next": {"": [2]}}, "2": {}}


def test_move_of_non_tail_relative_to_itself_is_rejected():
    # Used to detach the point AND leave its successor referenced twice.
    model = make_graph_model(
        {"0": 1, "1": {"next": {"": [2]}}, "2": {"next": {"": [3]}}, "3": {}}
    )
    graph = model.get_graph()

    with pytest.raises(GraphPointReferencePointInvalid):
        graph.move(model.points[2], model.points[2], "south")

    assert model.graph["2"] == {"next": {"": [3]}}


def test_insert_relative_to_itself_is_rejected():
    model = make_graph_model({"0": 1, "1": {}})
    graph = model.get_graph()

    with pytest.raises(GraphPointReferencePointInvalid):
        graph.insert(model.points[1], model.points[1], "south", "")


def test_insert_when_reference_already_points_at_the_point_is_rejected():
    # The double-insert producer of the self-reference corruption: the point's
    # "old successor" would be read as the point itself. Reachable through
    # concurrency (a stale write resurrecting a reference a trash removed,
    # followed by a restore).
    model = make_graph_model({"0": 1, "1": {"children": {"": [2]}}, "2": {}})
    graph = model.get_graph()

    with pytest.raises(GraphPointReferencePointInvalid):
        graph.insert(model.points[2], model.points[1], "child", "")

    assert model.graph == {"0": 1, "1": {"children": {"": [2]}}, "2": {}}


def test_insert_at_root_when_already_root_is_rejected():
    # Double root insert would make the root its own next.
    model = make_graph_model({"0": 1, "1": {}})
    graph = model.get_graph()

    with pytest.raises(GraphPointReferencePointInvalid):
        graph.insert(model.points[1], None, "south", "")

    assert model.graph == {"0": 1, "1": {}}


def test_move_onto_a_double_parented_reference_is_rejected():
    # Composition case: with a pre-existing double reference (1 -> 3 and
    # 2 -> 3), a legitimate-looking move of 3 south of 2 used to write
    # 3 -> 3. The insert guard now detects the surviving stale reference and
    # raises; in real flows the transaction rolls back the partial removal.
    model = make_graph_model(
        {"0": 1, "1": {"next": {"": [3]}}, "2": {"next": {"": [3]}}, "3": {}}
    )
    graph = model.get_graph()

    with pytest.raises(GraphPointReferencePointInvalid):
        graph.move(model.points[3], model.points[2], "south")

    # Whatever intermediate state the mock (transactionless) graph is left in,
    # no self-reference may have been written.
    assert 3 not in model.graph["3"].get("next", {}).get("", [])


def test_insert_of_point_referenced_anywhere_is_rejected():
    # The "ghost move" producer of the converging-reference corruption: the
    # point's entry was dropped by a stale write while a reference to it
    # survived. remove() splices nothing (the point is unkeyed), so the insert
    # would add a second incoming reference — and, north of a point upstream
    # of the surviving reference, a cycle.
    model = make_graph_model(
        {"0": 1, "1": {"next": {"": [2]}}, "2": {"next": {"": [3]}}}
    )
    ghost = make_point(3, model)
    graph = model.get_graph()

    with pytest.raises(GraphPointReferencePointInvalid):
        graph.insert(ghost, model.points[1], "north", "")

    assert model.graph == {"0": 1, "1": {"next": {"": [2]}}, "2": {"next": {"": [3]}}}


def test_move_of_ghost_point_with_surviving_reference_is_rejected():
    # Full reproduction of the customer corruption vector: chain
    # 1 -> 2(container, slot 0: 4 -> ghost 3) where ghost 3 lost its entry but
    # kept 4's reference. Moving the ghost north of 2 used to write
    # 1 -> 3 -> 2 while 4 -> 3 survived: a converging reference AND a cycle
    # (3 -> 2 -> child 4 -> 3).
    model = make_graph_model(
        {
            "0": 1,
            "1": {"next": {"": [2]}},
            "2": {"children": {"0": [4]}},
            "4": {"next": {"": [3]}},
        }
    )
    ghost = make_point(3, model)
    graph = model.get_graph()

    with pytest.raises(GraphPointReferencePointInvalid):
        graph.move(ghost, model.points[2], "north")

    assert model.graph == {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {"children": {"0": [4]}},
        "4": {"next": {"": [3]}},
    }


def test_move_relative_to_own_descendant_is_rejected():
    # Moving a container next to (or inside) one of its own descendants used
    # to loop the subtree back onto its ancestor — an instant cycle from a
    # perfectly valid graph, no concurrency required.
    initial = {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {"next": {"": [5]}, "children": {"0": [3]}},
        "3": {"next": {"": [4]}},
        "4": {},
        "5": {},
    }
    model = make_graph_model(dict(initial))
    graph = model.get_graph()

    # South of a direct child, south of a transitive chain member, and as a
    # child of a nested container are all rejected before any write.
    for reference_id, position in [(3, "south"), (4, "south"), (3, "child")]:
        with pytest.raises(GraphPointReferencePointInvalid):
            graph.move(model.points[2], model.points[reference_id], position)
        assert model.graph == initial


def test_insert_relative_to_own_descendant_is_rejected():
    model = make_graph_model(
        {
            "0": 1,
            "1": {"children": {"0": [2]}},
            "2": {},
        }
    )
    graph = model.get_graph()
    graph.remove(model.points[1], keep_info=True)

    with pytest.raises(GraphPointReferencePointInvalid):
        graph.insert(model.points[1], model.points[2], "south", "")


def test_insert_relative_to_unkeyed_reference_is_rejected():
    # The reference row can outlive its graph entry (deleted by a concurrent
    # transaction after the caller fetched it, or an unhealed orphan). Insert
    # used to KeyError midway; it must reject cleanly before any write.
    model = make_graph_model({"0": 1, "1": {}})
    unkeyed_reference = make_point(2, model)
    new_point = make_point(3, model)
    graph = model.get_graph()

    with pytest.raises(GraphPointReferencePointInvalid):
        graph.insert(new_point, unkeyed_reference, "south", "")

    assert model.graph == {"0": 1, "1": {}}


def test_cross_graph_move_locks_in_ascending_pk_order():
    # Two opposite-direction cross-graph moves must acquire the two container
    # locks in the same (ascending pk) order, or they can deadlock.
    from unittest.mock import patch

    from baserow.core.graph.handler import BaseGraphHandler

    def build_pair():
        model_a = make_graph_model({"0": 10, "10": {}})
        model_a.id = 1
        model_b = make_graph_model({"0": 20, "20": {}})
        model_b.id = 2
        return model_a, model_b

    for source_id, target_id in [(1, 2), (2, 1)]:
        model_a, model_b = build_pair()
        models = {1: model_a, 2: model_b}
        source, target = models[source_id], models[target_id]
        source_point = source.points[10 if source is model_a else 20]

        lock_order = []
        with patch.object(
            BaseGraphHandler,
            "_lock_instance_for_update",
            lambda self: lock_order.append(self.instance.id),
        ):
            source.get_graph().move(
                source_point,
                None,
                "south",
                "",
                target_graph=target.get_graph(),
            )

        # The patched lock records every call (the real method is idempotent
        # per handler); only the first acquisition of each container matters.
        first_acquisitions = list(dict.fromkeys(lock_order))
        assert first_acquisitions == [1, 2], (source_id, target_id, lock_order)
