from typing import Dict

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

    def save(self, update_fields=None):
        pass


class MockGraphPoint(GraphPointMixin):
    graph_parent_field_name = "model"

    def __init__(self, id, model):
        self.id = id
        self.model = model

    def __repr__(self):
        return "<MockGraphPoint id={}>".format(self.id)

    def get_parent(self):
        return self.model


def make_graph_model(graph: dict) -> MockGraphModel:
    """Build a MockGraphModel, registering a MockGraphPoint for every non-"0" key."""
    model = MockGraphModel(graph)
    for point_id in graph.keys():
        if point_id == "0":
            continue
        model.points[int(point_id)] = MockGraphPoint(int(point_id), model)
    return model
