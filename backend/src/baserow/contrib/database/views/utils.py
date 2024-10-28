from typing import Any, Dict

from django.db.models.aggregates import Aggregate


class AnnotatedAggregation:
    """
    A simple wrapper class for combining multiple annotations with an aggregation.
    This can be used in places where typically just an aggregation is returned,
    but must optionally be able to apply annotations to the same queryset.
    """

    def __init__(self, annotations: Dict[str, Any], aggregation: Aggregate):
        """
        :param annotations: The annotation which can be applied to the queryset.
        :param aggregation: The aggregate which must be applied to the queryset.
        """

        self.annotations = annotations
        self.aggregation = aggregation
