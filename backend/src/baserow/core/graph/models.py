from typing import Self

from django.db import models
from django.utils.translation import gettext_lazy as _

from baserow.core.cache import local_cache
from baserow.core.graph.handler import BaseGraphHandler
from baserow.core.graph.types import (
    GraphPointPosition,
    GraphPointPositionType,
    SerializedGraph,
)


class GraphModelMixin(models.Model):
    """
    A mixin that can be used to add a point graph to a model. The graph is stored as
    a JSON field and can be accessed via the get_graph method.
    """

    graph = models.JSONField(
        default=dict,
        db_default={},
        help_text="A JSON serialized graph containing the points and edges.",
    )

    class Meta:
        abstract = True

    def get_graph_handler(self):
        raise NotImplementedError("Subclasses must implement get_graph_handler method.")

    def get_graph(self) -> BaseGraphHandler:
        """
        Returns the shared graph handler for this model's ID within the current
        request.  A single handler is cached per (model_label, id) so that all
        callers within a request see the same in-memory graph mutations.

        If the cached handler was seeded by a *different* Python instance of the
        same row (e.g. a freshly fetched reference_element.page), we rebind it
        to ``self`` so that mutations remain visible via ``self.graph``.
        """

        handler_class = self.get_graph_handler()
        handler = local_cache.get(
            f"cached_graph_{self._meta.label}_{self.id}",
            lambda: handler_class(self),
        )
        if handler.instance is not self:
            # Another page object (same DB row, different Python object) seeded
            # the cache first.  Share the same graph dict so that subsequent
            # mutations made through the handler are visible on self.graph.
            self.graph = handler.instance.graph
            handler.instance = self
        return handler

    def print_graph(self, message=None, original=False):
        """
        Prints the graph in a pretty way. Useful for debug.
        """

        import pprint

        if message:
            print(message)

        if original:
            pprint.pprint(self.get_graph().graph, indent=2)
        else:
            pprint.pprint(self.get_graph().labeled_graph(), indent=2)

    def assert_reference(self, reference: SerializedGraph):
        """
        Used in test, compare the current graph with the given reference and
        raise an error if the graph doesn't match.
        """

        import pprint

        try:
            assert (
                self.get_graph().labeled_graph() == reference  # nosec B101
            ), "Failed to match the reference."
        except AssertionError:
            print("Failed to match the reference:")
            pprint.pprint(reference, indent=2)
            self.print_graph("Current graph:")
            raise


class GraphPointMixin:
    """
    A mixin that can be used to add graph point related methods to a model.

    Classes using this mixin must also inherit from Django's Model and implement
    the GraphPoint protocol (i.e., have `get_parent()` and `get_type()` methods).
    """

    def _get_graph(self) -> BaseGraphHandler:
        """
        A convenience method which return's our parent model
        (which implements the `GraphModelMixin`) graph.

        :return: A graph handler instance related to the parent model.
        """

        return self.get_parent().get_graph()

    @property
    def graph_point_label(self) -> str:
        """
        A convenience method used by the graph handler's `labeled_graph` method.
        If a graph point has a label, then it's used, otherwise we just return
        the model's type name.

        :return: A label which we can show in `labeled_graph`.
        """

        if hasattr(self, "label") and self.label:
            return self.label
        else:
            return self.get_type().type

    def get_previous_edge_name(self) -> str:
        """
        Returns the nearest `next` edge used to reach this point.
        """

        previous_positions = self.get_previous_positions()
        for _previous_point, position, output in reversed(previous_positions):
            if position == GraphPointPosition.SOUTH:
                return output
        return ""

    def get_place_name(self) -> str:
        """
        Returns the nearest parent place used to reach this point.
        """

        previous_positions = self.get_previous_positions()
        for _previous_point, position, output in reversed(previous_positions):
            if position == GraphPointPosition.CHILD:
                return output
        return ""

    def graph_point_edge_label(self, uid: str) -> str:
        """
        A convenience method used by the graph handler's `labeled_graph` method.
        By default, we return an empty string, it's up to `GraphPointMixin` classes
        to determine (if at all) what their point edge labels should be.

        :param uid: The uid of the edge for which we want to get the label.
        :return: A label which we can show in `labeled_graph` for the edge
            with the given uid.
        """

        return _("Unlabeled")

    @property
    def is_root_point(self) -> bool:
        """
        Returns True if the point is a root point in the graph. A root point is
        always at key "0" in the graph and is the starting point of the graph.
        There is only ever one root point.

        :return: True if the point is the root point.
        """

        return self._get_graph().get_point_at_position(None, "south", "").id == self.id

    @property
    def is_nested_point(self) -> bool:
        """
        Returns True if the point is nested in the graph. A nested point is a point
        that is not at the root level of the graph, but is a child of another point
        (or a sibling within a container's next chain).

        :return: True if the point is nested.
        """

        return any(
            position == GraphPointPosition.CHILD
            for _previous_point, position, _output in self.get_previous_positions()
        )

    def get_previous_points(self) -> list[Self]:
        """
        Returns the points before the current point. A previous point can be a
        `previous point` or a `parent point`.
        """

        return [
            previous_point
            for previous_point, _position, _output in self.get_previous_positions()
            if previous_point is not None
        ]

    def get_child_points(self) -> list[Self]:
        """
        Returns the direct children of the given point.
        """

        return self._get_graph().get_children(self)

    def get_sibling_points(self) -> list[Self]:
        """
        Returns the siblings of the given point.
        """

        return self._get_graph().get_siblings(self)

    def get_previous_positions(
        self,
    ) -> list[tuple[Self | None, GraphPointPositionType, str]]:
        """
        Returns the path of graph positions used to reach this point, ordered
        from root to this point. Uses the cached previous-position map so the
        path is resolved with O(depth) dict lookups.
        """

        return self._get_graph().get_previous_positions(self) or []

    def get_parent_point(self) -> Self | None:
        """
        Returns the direct parent container point, or ``None`` if this point
        has no parent. Uses the cached previous-position map so the chain is
        resolved with O(depth) dict lookups rather than a full graph traversal.
        """

        for previous_point, position, _output in reversed(
            self.get_previous_positions()
        ):
            if position == GraphPointPosition.CHILD:
                return previous_point
        return None

    def get_parent_points(self) -> list[Self]:
        """
        Returns the ancestor container points that contain this point, ordered
        from outermost to innermost (direct parent last). Uses the cached
        previous-position map so the chain is resolved with O(depth) dict
        lookups rather than a full graph traversal per element.
        """

        return [
            previous_point
            for previous_point, position, _output in self.get_previous_positions()
            if position == GraphPointPosition.CHILD
        ]

    def get_next_points(self, output_uid: str | None = None) -> list[Self]:
        """
        Returns all points which directly follow this point in the workflow.
        A list of points is returned as there can be multiple points that follow this one,
        for example when there are multiple branches in the workflow.

        :param output_uid: filter points only for this output uid.
        """

        return self._get_graph().get_next_points(self, output_uid)
