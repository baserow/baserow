from django.db import models

from baserow.core.cache import local_cache


class GraphModelMixin(models.Model):
    """
    A mixin that can be used to add a node graph to a model. The graph is stored as
    a JSON field and can be accessed via the get_graph method.
    """

    # Does this model instance, which implements our mixin, support the concept
    # of edges between nodes? If False, the graph will be a simple tree structure.
    # If True, the graph can contain named edges between nodes.
    supports_edges: bool = False

    graph = models.JSONField(default=dict, help_text="Contains the node graph.")

    class Meta:
        abstract = True

    def get_graph_handler(self):
        raise NotImplementedError("Subclasses must implement get_graph_handler method.")

    def get_graph(self):
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

    def assert_reference(self, reference):
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
            self.print("Current graph:")
            raise
