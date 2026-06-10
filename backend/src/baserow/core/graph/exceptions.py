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
