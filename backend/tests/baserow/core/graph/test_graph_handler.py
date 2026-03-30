from decimal import Decimal

from baserow.core.graph.handler import BaseGraphHandler
from tests.baserow.core.graph.fixtures import make_graph_model


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
