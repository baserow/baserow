from typing import Dict

import pytest

from baserow.core.graph.handler import BaseGraphHandler
from baserow.core.graph.models import GraphPointMixin


class MockGraphHandler(BaseGraphHandler):
    def get_point_map(self) -> Dict[int, "MockGraphPoint"]:
        return self.instance.points


class MockGraphModel:
    def __init__(self, graph):
        self.id = 1
        self.graph = graph
        self.points = {}

    def get_graph_handler(self):
        return MockGraphHandler

    def get_graph(self):
        return self.get_graph_handler()(self)


class MockGraphPoint(GraphPointMixin):
    graph_parent_field_name = "model"

    def __init__(self, id, model):
        self.id = id
        self.model = model

    def __repr__(self):
        return "<MockGraphPoint id={}>".format(self.id)

    def get_parent(self):
        return self.model


@pytest.fixture()
def graph_model_fixture():
    graph = {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {
            "next": {
                "uuid1": [3],
                "uuid2": [5],
                "": [4],
            }
        },
        "3": {},
        "5": {},
        "4": {"next": {"": [6]}},
        "6": {"children": {"": [7], "0": [8], "1": [9]}},
        "7": {},
        "8": {},
        "9": {"next": {"": [10]}},
        "10": {"next": {"": [11]}},
        "11": {},
    }

    model = MockGraphModel(graph)
    for point_id in graph.keys():
        if point_id == "0":
            continue
        model.points[int(point_id)] = MockGraphPoint(int(point_id), model)
    return model


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
