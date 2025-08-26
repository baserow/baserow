import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from django.db.models import BooleanField, Q
from django.db.models.expressions import F, Value
from django.db.models.functions import Mod

from opentelemetry import trace

from baserow.contrib.database.formula.expression_generator.django_expressions import (
    FileNameContainsExpr,
)
from baserow.core.telemetry.utils import baserow_trace_methods

if TYPE_CHECKING:
    from baserow.contrib.database.table.models import GeneratedTableModel

FILTER_TYPE_AND = "AND"
FILTER_TYPE_OR = "OR"


tracer = trace.get_tracer(__name__)


def parse_ids_from_csv_string(value: str) -> list[int]:
    """
    Parses the provided value and returns a list of integers that represent ids. If a
    token is not a digit, it is ignored.

    :param value: The value that has been provided by the user.
    :return: A list of integers that represent ids.
    """

    try:
        return [int(v) for v in value.split(",") if v.strip().isdigit()]
    except ValueError:
        return []


def map_ids_from_csv_string(
    value_string: str, mapping: Optional[dict] = None
) -> list[Union[str, int]]:
    """
    Parses the provided value if needed and returns a list ids.

    :param value_string: The value that has been provided by the user.
    :param mapping: Key is given option id, and the value is th target option id.
    :return: A list of integers that represent ids.
    """

    # There is a small chance the value is an int in case a raw ID was provided in
    # the row coloring, where the filters are stored as JSON. Cast it to a string to
    # make it compatible.
    if not isinstance(value_string, str):
        value_string = str(value_string)

    parsed_values = []
    for value in value_string.split(","):
        # In some cases, the select option ID is a string, like with the Airtable
        # import. If the value can be found in the mapping, then we'll directly use
        # that value.
        if value in mapping:
            parsed_values.append(str(mapping[value]))
            continue

        if value.strip().isdigit():
            # Convert to int because the serialized value can be a string, but the key
            # in the mapping is an int.
            value = int(value)
            if value in mapping:
                parsed_values.append(str(mapping[value]))

    return parsed_values


class AnnotatedQ:
    """
    A simple wrapper class combining a params for a Queryset.annotate call with a
    django Q object to be used in combination with FilterBuilder to dynamically build up
    filters which also require annotations.
    """

    def __init__(self, annotation: Dict[str, Any], q: Union[Q, Dict[str, Any]]):
        """
        :param annotation: A dictionary which can be unpacked into a django
            Queryset.annotate call. This will only happen when using
            FilterBuilder.apply_to_queryset.
        :param q: a Q object or kwargs which will used to create a Q object.
        """

        self.annotation = annotation or {}
        if isinstance(q, Q):
            self.q = q
        else:
            self.q = Q(**q)

    def __invert__(self):
        return AnnotatedQ(self.annotation, ~self.q)


OptionallyAnnotatedQ = Union[Q, AnnotatedQ]


class FilterBuilder:
    """
    Combines together multiple Q or AnnotatedQ filters into a single filter which
    will AND or OR the provided filters together based on the filter_type
    parameter. When applied to a queryset it will also annotate the queryset
    prior to filtering with the merged annotations from AnnotatedQ filters.
    """

    def __init__(self, filter_type: str = FILTER_TYPE_AND):
        """

        :param filter_type: Either field_filters.FILTER_TYPE_AND or
            field_filters.FILTER_TYPE_OR which dictates how provided Q or AnnotatedQ
            filters will be combined together.
            For type OR they will be ORed together when applied to a filter set,
            for type AND they will be ANDed together.
        """

        if filter_type not in [FILTER_TYPE_AND, FILTER_TYPE_OR]:
            raise ValueError(f"Unknown filter type {filter_type}.")

        self._annotation: Dict[str, Any] = {}
        self._q_filters = Q()
        self._filter_type = filter_type

    def filter(
        self, q: Union[Q, OptionallyAnnotatedQ, "FilterBuilder"]
    ) -> "FilterBuilder":
        """
        Adds a Q, an AnnotatedQ or another FilterBuilder filter into this
        builder to be joined together with existing filters based on the
        builders `filter_type`.

        Annotations on provided AnnotatedQ's are merged together with any
        previously supplied annotations via dict unpacking and merging.

        :param q: One of compatible object types that provide Q expressions to
            be joined together.
        :return: The updated FilterBuilder with the provided filter applied.
        """

        if isinstance(q, FilterBuilder):
            self._annotate(q._annotation)
            self._filter(q._q_filters)
        elif isinstance(q, AnnotatedQ):
            self._annotate(q.annotation)
            self._filter(q.q)
        else:
            self._filter(q)
        return self

    def apply_to_queryset(self, queryset):
        """
        Applies all of the Q and AnnotatedQ filters previously given to this
        FilterBuilder by first applying all annotations from AnnotatedQ's and then
        filtering with a Q filter resulting from the combination of all filters ANDed or
        ORed depending on the filter_type attribute.

        :param queryset: The queryset to annotate and filter.
        :return: The annotated and filtered queryset.
        """

        filtered_queryset = queryset.annotate(**self._annotation).filter(
            self._q_filters
        )

        # When using OR conditions in filters that involve joined tables, the SQL query
        # may produce duplicate rows because multiple join paths can match the same
        # record. Applying distinct() ensures we return only unique results.
        return filtered_queryset.distinct()

    def get_filters_and_annotations(self) -> Tuple[Q, Dict[str, Any]]:
        """
        Returns the filters which have been applied to this FilterBuilder and
        the annotations which have been merged together from all AnnotatedQ's.

        :return: A tuple containing the Q filters and the annotations.
        """

        return self._q_filters, self._annotation

    def _annotate(self, annotation_dict: Dict[str, Any]):
        self._annotation = {**self._annotation, **annotation_dict}

    def _filter(self, q_filter: Q):
        if self._filter_type == FILTER_TYPE_AND:
            self._q_filters &= q_filter
        elif self._filter_type == FILTER_TYPE_OR:
            self._q_filters |= q_filter
        else:
            raise ValueError(f"Unknown filter type {self._filter_type}.")


def contains_filter(
    field_name, value, model_field, _, validate=True
) -> OptionallyAnnotatedQ:
    value = value.strip()
    # If an empty value has been provided we do not want to filter at all.
    if value == "":
        return Q()
    if validate:
        model_field.get_prep_value(value)
    return Q(**{f"{field_name}__icontains": value})


def contains_word_filter(field_name, value, model_field, _) -> OptionallyAnnotatedQ:
    value = value.strip()
    # If an empty value has been provided we do not want to filter at all.
    if value == "":
        return Q()
    # make sure to escape the value as it may contain regex characters
    value = re.escape(value)
    model_field.get_prep_value(value)
    return Q(**{f"{field_name}__iregex": rf"\m{value}\M"})


def filename_contains_filter(field_name, value, _, field) -> OptionallyAnnotatedQ:
    value = value.strip()
    # If an empty value has been provided we do not want to filter at all.
    if value == "":
        return Q()
    # Check if the model_field has a file which matches the provided filter value.
    annotation_query = FileNameContainsExpr(
        F(field_name), Value(f"%{value}%"), output_field=BooleanField()
    )
    hashed_value = hash(value)
    return AnnotatedQ(
        annotation={
            f"{field_name}_matches_visible_names_{hashed_value}": annotation_query
        },
        q={f"{field_name}_matches_visible_names_{hashed_value}": True},
    )


def is_even_and_whole_number_filter(
    field_name, value, _, field
) -> OptionallyAnnotatedQ:
    return AnnotatedQ(
        annotation={f"{field_name}_is_even_and_whole": Mod(F(f"{field_name}"), 2)},
        q={f"{field_name}_is_even_and_whole": 0},
    )


class FilterGroupNode:
    """
    Utility class to construct a tree made of filters and groups of filters.
    """

    def __init__(
        self,
        filter_builder: FilterBuilder,
        parent: Optional["FilterGroupNode"] = None,
    ):
        self.filter_builder = filter_builder
        self.parent = parent
        self.children: List["FilterGroupNode"] = []
        if parent:
            parent.children.append(self)


class GroupedFiltersAdapter(ABC):
    """
    An adapter class which provides a way to get a list of filters and groups
    to construct a AdvancedFilterBuilder from.
    """

    def __init__(self, instance: any, model: "GeneratedTableModel", **kwargs):
        self.instance = instance
        self.model = model

    @property
    @abstractmethod
    def filters(self):
        """Returns a list of filters."""

    @property
    @abstractmethod
    def groups(self):
        """Returns a list of groups."""

    @property
    def filter_type(self):
        return self.instance.filter_type

    @abstractmethod
    def get_q_from_filter(self, _filter) -> Union[Q, AnnotatedQ]:
        """
        Returns one of the compatible types to be applied to a filter builder
        starting from a filter.
        """


class AdvancedFilterBuilder(metaclass=baserow_trace_methods(tracer)):
    """
    This utility class constructs a filter builder using an instance of
    GroupedFiltersAdapter. While the FilterBuilder class combines filters using
    only a single AND or OR operation, this class takes it a step further. It
    can arrange different filter groups into a tree structure, where each group
    has its own distinct filter type. This class ensures that the filters and
    the annotations are applied in the correct order.
    """

    def __init__(self, adapter: GroupedFiltersAdapter):
        self.adapter = adapter

    def construct_filter_builder(self) -> FilterBuilder:
        """
        Constructs a filter builder for the provided instance and model.
        This method reconstructs the tree of filters in memory and applied
        the filters in the correct order.

        :return: The created filter builder.
        """

        adapter = self.adapter
        root_filter_builder = FilterBuilder(filter_type=adapter.filter_type)
        root_node = FilterGroupNode(root_filter_builder, parent=None)
        groups_by_id = {None: root_node}

        # Construct the tree of filter groups from the database so we can
        # later apply filters in the correct order.
        # NOTE: This code assumes that groups are returned with parent groups
        # before their children.

        for group in adapter.groups:
            parent_node = groups_by_id[group.parent_group_id]
            group_filter_builder = FilterBuilder(filter_type=group.filter_type)
            groups_by_id[group.id] = FilterGroupNode(
                group_filter_builder, parent=parent_node
            )

        # At first, apply the filters to all the filter builder groups. The order
        # does not matter here because the filters in the same groups are always
        # combined with the same filter type.
        for _filter in adapter.filters:
            q_filter = self.adapter.get_q_from_filter(_filter)

            group_node = groups_by_id[_filter.group_id]
            group_filter_builder = group_node.filter_builder
            group_filter_builder.filter(q_filter)

        # recursively construct the filter builder from the tree of filter groups.
        return self._construct_filter_builder_from_tree(root_node)

    def _construct_filter_builder_from_tree(
        self, node: FilterGroupNode
    ) -> FilterBuilder:
        """
        Constructs a filter builder from a tree of FilterGroupNodes recursively.
        It first apply all the filters to the leaves of the tree, and then
        combines the filter builders in the correct order.
        """

        filter_builder = node.filter_builder
        if node.children:
            for child in node.children:
                child_filter_builder = self._construct_filter_builder_from_tree(child)
                filter_builder.filter(child_filter_builder)

        return filter_builder
