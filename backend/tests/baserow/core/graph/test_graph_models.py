from django.test import override_settings

import pytest

from baserow.core.cache import local_cache
from baserow.core.graph.models import GraphModelMixin
from tests.baserow.core.graph.fixtures import MockGraphHandler


class MockCachedGraphModel:
    """
    Minimal model-like object that exercises the real GraphModelMixin.get_graph()
    (including local_cache logic), unlike MockGraphModel which has its own simple
    implementation.
    """

    class _meta:
        label = "test.MockCachedGraphModel"

    def __init__(self, graph=None, model_id=1):
        self.id = model_id
        self.graph = graph if graph is not None else {}
        self.points = {}

    def get_graph_handler(self):
        return MockGraphHandler

    get_graph = GraphModelMixin.get_graph

    def save(self, update_fields=None):
        pass


@override_settings(BASEROW_USE_LOCAL_CACHE=True)
def test_get_graph_permutations():
    # ── Case 1: cache miss — first call creates a handler bound to self ───────
    with local_cache.context():
        model = MockCachedGraphModel({"0": 1}, model_id=1)
        handler = model.get_graph()
        assert handler.instance is model

    # ── Case 2: cache hit, same instance — identical handler returned ─────────
    with local_cache.context():
        model = MockCachedGraphModel({"0": 1}, model_id=2)
        assert model.get_graph() is model.get_graph()
        assert model.get_graph().instance is model

    # ── Case 3: cache hit, different instance — handler is rebound ───────────
    # Simulates Django producing two Python objects for the same DB row, e.g.
    # service's `page` vs. `reference_element.page` after a fresh ORM fetch.
    with local_cache.context():
        graph_a = {"0": 1}
        instance_a = MockCachedGraphModel(graph_a, model_id=42)
        handler_a = instance_a.get_graph()

        graph_b = {"0": 1}
        instance_b = MockCachedGraphModel(graph_b, model_id=42)
        handler_b = instance_b.get_graph()

        # Same cached handler, rebound to instance_b.
        assert handler_b is handler_a
        assert handler_b.instance is instance_b
        # instance_b.graph now shares the authoritative dict so that mutations
        # through the handler are visible on instance_b.
        assert instance_b.graph is graph_a
        handler_b.graph["5"] = {"test": True}
        assert instance_b.graph["5"] == {"test": True}


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
