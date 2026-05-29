from django.core.exceptions import ObjectDoesNotExist


class GraphPointDoesNotExist(ObjectDoesNotExist):
    """
    Raised when a `GraphPoint` does not exist in the database.
    """


class GraphPointNotFoundInGraph(Exception):
    """
    Raised when we try to access a `GraphPoint` that does
    exist in the database, but it's not present in the graph.
    """


class GraphPointReferencePointInvalid(Exception):
    """
    Raised when trying to use an invalid reference point.
    """


class GraphConsistencyError(Exception):
    """
    Raised when the graph's node keys are out of sync with the DB.
    Only raised when settings.DEBUG is True.
    """

    def __init__(self, instance, stale, missing):
        self.stale = stale
        self.missing = missing
        super().__init__(
            f"Graph for {instance} is inconsistent. "
            f"Stale (in graph, not in DB): {stale}. "
            f"Missing (in DB, not in graph): {missing}."
        )
