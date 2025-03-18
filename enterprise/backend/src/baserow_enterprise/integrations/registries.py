from baserow.contrib.database.fields.exceptions import (
    FieldTypeAlreadyRegistered,
    FieldTypeDoesNotExist,
)
from baserow.contrib.database.fields.registries import FieldAggregationType, FieldType
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


class GroupedAggregationGroupByRegistry(Registry[FieldType]):
    """
    The main registry for storing field types compatible
    with the grouped aggregate service to be used as group by
    fields.
    """

    name = "grouped_aggregations_group_by"
    does_not_exist_exception_class = FieldTypeDoesNotExist
    already_registered_exception_class = FieldTypeAlreadyRegistered


grouped_aggregation_group_by_registry: GroupedAggregationGroupByRegistry = (
    GroupedAggregationGroupByRegistry()
)
