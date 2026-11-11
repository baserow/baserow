from typing import Iterable

from baserow.core.cache import local_cache
from baserow.core.graph.handler import BaseGraphHandler
from baserow.core.graph.models import GraphPointMixin


class MockGraphHandler(BaseGraphHandler):
    def get_all_points(self) -> Iterable["MockGraphPoint"]:
        return self.instance.points.values()


class MockGraphModel:
    class _meta:
        label = "test.MockGraphModel"

    def __init__(self, graph):
        self.id = 1
        self.graph = graph
        self.points = {}
        local_cache.delete(BaseGraphHandler.generate_point_map_cache_key(self))

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


def make_point(pid: int, model: MockGraphModel) -> MockGraphPoint:
    """Create a MockGraphPoint, register it on the model, and return it."""
    p = MockGraphPoint(pid, model)
    model.points[pid] = p
    local_cache.delete(BaseGraphHandler.generate_point_map_cache_key(model))
    return p


def make_graph_model(graph: dict) -> MockGraphModel:
    """Build a MockGraphModel, registering a MockGraphPoint for every non-"0" key."""
    model = MockGraphModel(graph)
    for point_id in graph.keys():
        if point_id == "0":
            continue
        model.points[int(point_id)] = MockGraphPoint(int(point_id), model)
    return model
