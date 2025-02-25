from typing import Any, Dict

from django.db.models.aggregates import Aggregate, Count


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


class DistributionAggregation:
    """
    Performs the equivalent of a SELECT field, count(*) FROM table GROUP BY field
    on the provided queryset.
    """

    def __init__(self, group_by):
        """
        :param group_by: The name of the queryset field that contains the values
            that need to be grouped by
        """

        self.group_by = group_by

    def calculate(self, queryset, limit=10):
        """
        Calculates the distribution of values in the `group_by` field in the queryset.
        Returns the top tep results, sorted by count descending.
        :param queryset: The queryset to calculate the distribution on
        :param limit: The number of results to return.
        """

        # Disable prefetch behaviors for this query
        queryset._multi_field_prefetch_related_funcs = []
        return list(
            queryset.values(self.group_by)
            .annotate(count=Count("*"))
            .order_by("-count", self.group_by)
            .values_list(self.group_by, "count")[:limit]
        )
