import pytest


@pytest.mark.parametrize(
    "point_id, expected_place",
    [
        (1, ""),
        (2, ""),
        (3, ""),
        (4, ""),
        (5, ""),
        (6, ""),
        (7, ""),
        (8, "0"),
        (9, "1"),
        (10, "1"),
        (11, "1"),
    ],
)
def test_graph_model_get_place_name(point_id, expected_place, graph_model_fixture):
    model = graph_model_fixture
    assert model.points[point_id].get_place_name() == expected_place


@pytest.mark.parametrize(
    "point_id, expected_edge",
    [
        (1, ""),
        (2, ""),
        (3, "uuid1"),
        (4, ""),
        (5, "uuid2"),
        (6, ""),
        (7, ""),
        (8, ""),
        (9, ""),
        (10, ""),
        (11, ""),
    ],
)
def test_graph_model_get_previous_edge_name(
    point_id, expected_edge, graph_model_fixture
):
    model = graph_model_fixture
    assert model.points[point_id].get_previous_edge_name() == expected_edge
