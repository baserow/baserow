from decimal import Decimal

from baserow.core.graph.handler import BaseGraphHandler
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

    # Insert another child of p2 in same place "0" — chains after p4
    p5 = make_point(5, model)
    graph.insert(p5, p2, "child", output="0")
    assert model.graph["2"]["children"]["0"] == [4]
    assert model.graph["4"]["next"][""] == [5]

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

    # Insert north of p4 which is a child head — new point replaces p4 in
    # children dict, p4 becomes new point's next.
    p9 = make_point(9, model)
    graph.insert(p9, p4, "north", output="")
    assert model.graph["2"]["children"]["0"] == [9]
    assert model.graph["9"]["next"][""] == [4]


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


def test_get_parent_map_permutations():
    model = make_graph_model({})
    graph = model.get_graph()

    # Empty graph — no containers, no children
    assert graph.get_parent_map() == {}

    # Add a flat chain: 1 → 2 → 3 (no children) — still empty
    p1 = make_point(1, model)
    graph.insert(p1, None, "south", output="")
    p2 = make_point(2, model)
    graph.insert(p2, p1, "south", output="")
    p3 = make_point(3, model)
    graph.insert(p3, p2, "south", output="")
    assert graph.get_parent_map() == {}

    # Insert p4 as child of p2 in place "0" — p4 maps to p2
    p4 = make_point(4, model)
    graph.insert(p4, p2, "child", output="0")
    assert graph.get_parent_map() == {4: 2}

    # Chain p5 south of p4 (still under p2) — p5 also maps to p2
    p5 = make_point(5, model)
    graph.insert(p5, p2, "child", output="0")
    assert graph.get_parent_map() == {4: 2, 5: 2}

    # Add p6 as child of p2 in a different place "1"
    p6 = make_point(6, model)
    graph.insert(p6, p2, "child", output="1")
    assert graph.get_parent_map() == {4: 2, 5: 2, 6: 2}

    # Add p7 as child of p4 (nested) — p7 maps to p4, not p2
    p7 = make_point(7, model)
    graph.insert(p7, p4, "child", output="")
    assert graph.get_parent_map() == {4: 2, 5: 2, 6: 2, 7: 4}

    # None graph — should return empty without raising
    model.graph = None
    assert graph.get_parent_map() == {}


def test_graph_handler_get_order_map(graph_model_fixture):
    model = graph_model_fixture
    assert BaseGraphHandler.get_order_map(model.graph) == {
        1: Decimal("1.00000000000000000000"),
        2: Decimal("2.00000000000000000000"),
        3: Decimal("1.00000000000000000000"),
        5: Decimal("1.00000000000000000000"),
        12: Decimal("2.00000000000000000000"),
        4: Decimal("3.00000000000000000000"),
        6: Decimal("4.00000000000000000000"),
        7: Decimal("1.00000000000000000000"),
        8: Decimal("1.00000000000000000000"),
        9: Decimal("1.00000000000000000000"),
        10: Decimal("2.00000000000000000000"),
        11: Decimal("3.00000000000000000000"),
    }
