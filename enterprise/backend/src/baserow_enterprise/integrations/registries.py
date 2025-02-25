from baserow.contrib.database.fields.registries import FieldAggregationType
from baserow.contrib.database.views.exceptions import (
    AggregationTypeAlreadyRegistered,
    AggregationTypeDoesNotExist,
)
from baserow.core.registry import Registry


class GroupedAggregationTypeRegistry(Registry[FieldAggregationType]):
    """
    The main registry for storing aggregation types compatible
    with the grouped aggregate service.
    """

    name = "grouped_aggregations"
    does_not_exist_exception_class = AggregationTypeDoesNotExist
    already_registered_exception_class = AggregationTypeAlreadyRegistered


grouped_aggregation_registry: GroupedAggregationTypeRegistry = (
    GroupedAggregationTypeRegistry()
)
