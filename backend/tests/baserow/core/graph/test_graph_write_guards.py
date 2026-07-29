"""
Invariant guards at the graph write chokepoint. These scenarios used to
silently corrupt the graph (they are the reproduced root causes of the
self-referencing-point and ghost-point customer corruptions); they must now
raise so the surrounding transaction rolls back.
"""

import pytest

from baserow.core.graph.exceptions import GraphPointReferencePointInvalid
from tests.baserow.core.graph.fixtures import make_graph_model


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
