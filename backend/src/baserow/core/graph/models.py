from typing import Self

from django.db import models

from baserow.core.cache import local_cache
from baserow.core.graph.handler import BaseGraphHandler
from baserow.core.graph.types import SerializedGraph


class GraphModelMixin(models.Model):
    """
    A mixin that can be used to add a point graph to a model. The graph is stored as
    a JSON field and can be accessed via the get_graph method.
    """

    graph = models.JSONField(
        default=dict,
        help_text="A JSON serialized graph containing the points and edges.",
    )

    class Meta:
        abstract = True

    def get_graph_handler(self):
        raise NotImplementedError("Subclasses must implement get_graph_handler method.")

    def get_graph(self) -> BaseGraphHandler:
        """
        Returns the graph. Use the same graph instance related to the model
        ID regardless of the model instance.
        """

        handler = self.get_graph_handler()
        return local_cache.get(
            f"cached_graph_{self.id}",
            lambda: handler(self),
        )

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

        if hasattr(self, "label"):
            return self.label
        else:
            return self.get_type().type

    def get_previous_edge_name(self) -> str:
        """
        Responsible for walking backwards to the previous point, and assuming
        it has a `next` in its point info, finding the edge that `self` is along.
        """

        previous_points = self.get_previous_points()
        if not previous_points:
            return ""

        previous_point = previous_points[-1]
        previous_point_info = self._get_graph().get_info(previous_point.id)
        previous_point_next_info = previous_point_info.get("next", {})
        for edge_name, point_ids_on_edge in previous_point_next_info.items():
            if self.id in point_ids_on_edge:
                return edge_name

        return ""

    def get_place_name(self) -> str:
        """
        Responsible for walking backwards, starting at `self`, and finding the
        first point which has a position of "child". This point will be inside
        point info containing "children", and will have a place name to return.
        """

        # Collect all previous points, and add this current point to the end.
        previous_points_and_self = self.get_previous_points() + [self]

        # Reverse it, so we start with our current point, and we can
        # walk backwards through the hierarchy one point at a time.
        previous_points_and_self.reverse()
        for point in previous_points_and_self:
            # Get this point's position. The first child that we find
            # will be the immediate point along the same edge.
            _, position, output = self.get_parent().get_graph().get_position(point)
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

        return ""

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
        that is not at the root level of the graph, but is a child of another point.

        :return: True if the point is nested.
        """

        reference_point_id, position, output = self._get_graph().get_position(self)
        return position == "child"

    def get_previous_points(self) -> list[Self]:
        """
        Returns the points before the current point. A previous point can be a
        `previous point` or a `parent point`.
        """

        return [
            position[0] for position in self._get_graph().get_previous_positions(self)
        ]

    def get_child_points(self) -> list[Self]:
        """
        Returns the direct children of the given point.
        """

        return self._get_graph().get_children(self)

    @property
    def children(self) -> models.QuerySet[Self]:
        """
        Provides a compatibility interface which we used to have on models with a
        parent <-> child relationship in the ORM.

        :return: A QuerySet of models which are a child of `self`.
        """

        child_ids = [child.id for child in self.get_child_points()]
        return self._get_graph().base_point_class.objects.filter(pk__in=child_ids)

    def get_sibling_points(self) -> list[Self]:
        """
        Returns the siblings of the given point.
        """

        return self._get_graph().get_siblings(self)

    def get_parent_point(self) -> Self | None:
        """
        A convenience method which uses `get_parent_points` to
        return the first parent, or `None`.
        """

        point_ancestry = self.get_parent_points()
        return point_ancestry[0] if point_ancestry else None

    def get_parent_points(self) -> list[Self]:
        """
        Returns the ancestors of this point which are the container points that contain
        the current point instance.
        """

        return [
            position[0]
            for position in self._get_graph().get_previous_positions(self)
            if position[1] == "child"
        ]

    def get_next_points(self, output_uid: str | None = None) -> list[Self]:
        """
        Returns all points which directly follow this point in the workflow.
        A list of points is returned as there can be multiple points that follow this one,
        for example when there are multiple branches in the workflow.

        :param output_uid: filter points only for this output uid.
        """

        return self._get_graph().get_next_points(self, output_uid)
