from typing import TYPE_CHECKING, Type, Union

from django.db.models import Q

from baserow.contrib.database.fields.field_filters import (
    AnnotatedQ,
    FilterBuilder,
    GroupedFiltersAdapter,
)
from baserow.contrib.database.views.registries import view_filter_type_registry
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)

if TYPE_CHECKING:
    from baserow.contrib.database.table.models import GeneratedTableModel


class LocalBaserowServiceGroupedFiltersAdapter(GroupedFiltersAdapter):
    """
    A `GroupedFiltersAdapter` implementation for `LocalBaserow` services. It exposes
    the service's stored filters and filter groups to the `AdvancedFilterBuilder` so
    they can be applied to a queryset with correct nesting and per-group AND/OR
    operators.

    Unlike the views adapter, a service filter's `value` may be a runtime formula which
    must be resolved against the `dispatch_context` before it can be turned into a `Q`.
    """

    def __init__(
        self,
        service,
        model: Type["GeneratedTableModel"],
        dispatch_context: DispatchContext,
        **kwargs,
    ):
        super().__init__(service, model, **kwargs)
        self.dispatch_context = dispatch_context

    @property
    def filters(self):
        return self.instance.service_filters_with_untrashed_fields

    @property
    def groups(self):
        return self.instance.service_filter_groups.all()

    def get_q_from_filter(self, service_filter) -> Union[Q, AnnotatedQ]:
        field_object = self.model._field_objects[service_filter.field_id]
        field_name = field_object["name"]
        model_field = self.model._meta.get_field(field_name)
        view_filter_type = view_filter_type_registry.get(service_filter.type)

        try:
            resolved_value = resolve_formula(
                service_filter.value,
                formula_runtime_function_registry,
                self.dispatch_context,
            )
            values, operator = self.get_filter_values(resolved_value, view_filter_type)
        except Exception as exc:
            raise ServiceImproperlyConfiguredDispatchException(
                f"The {field_name} service filter formula can't be resolved: {exc}"
            ) from exc

        if len(values) == 1:
            return view_filter_type.get_filter(
                field_name, values[0], model_field, field_object["field"]
            )
        builder = FilterBuilder(operator)
        for value in values:
            builder.filter(
                view_filter_type.get_filter(
                    field_name, value, model_field, field_object["field"]
                )
            )
        q, annotations = builder.get_filters_and_annotations()
        return AnnotatedQ(annotations, q)

    def get_filter_values(self, value, view_filter_type):
        """Let each operator prepare its resolved formula value."""
        return [view_filter_type.prepare_value(value)], "AND"


MAX_FIELD_ID = 2**63 - 1


def get_unavailable_field_ids(conditions, service) -> set[int]:
    """
    Return the condition field ids that can't be applied to the service's table
    anymore: the field is trashed, permanently deleted, or wasn't available when
    the configuration was imported (stored as 0). Fields of another table aren't
    unavailable, they are invalid.
    """

    from baserow.contrib.database.fields.models import Field

    field_ids = {
        condition.get("field")
        for condition in conditions
        if isinstance(condition, dict)
        and isinstance(condition.get("field"), int)
        and not isinstance(condition.get("field"), bool)
        # Ids outside the column's range are left for the serializer to reject.
        and 0 <= condition.get("field") <= MAX_FIELD_ID
    }
    if not field_ids:
        return set()
    existing = {
        field_id: (table_id, trashed)
        for field_id, table_id, trashed in Field.objects_and_trash.filter(
            id__in=field_ids
        ).values_list("id", "table_id", "trashed")
    }
    # Skipping such a condition can't widen access: visitors can already clear the
    # filter value, so contributed conditions never restrict what they may see.
    return {
        field_id
        for field_id in field_ids
        if field_id not in existing
        or (existing[field_id][0] == service.table_id and existing[field_id][1])
    }


def get_deleted_field_ids(field_ids) -> set[int]:
    """Return the given field ids which don't exist, not even trashed."""

    from baserow.contrib.database.fields.models import Field

    field_ids = set(field_ids)
    if not field_ids:
        return set()
    return field_ids - set(
        Field.objects_and_trash.filter(id__in=field_ids).values_list("id", flat=True)
    )


def has_applicable_conditions(group, service) -> bool:
    """Whether a transient group has a condition on a field still available."""

    conditions = group.get("filters") or []
    unavailable = get_unavailable_field_ids(conditions, service)
    return any(
        not (isinstance(condition, dict) and condition.get("field") in unavailable)
        for condition in conditions
    )


def validate_runtime_filter_group(group, service):
    """
    Validate a transient group's shape, ancestry, fields, operators and formulas.

    Conditions on unavailable fields (see `get_unavailable_field_ids`) are kept by
    the caller and only their operator and group are validated. They aren't
    returned, so they don't apply until the field is restored. Each returned
    condition has the `index` of its position in the group's filters.
    """

    from rest_framework.exceptions import ValidationError

    from baserow.contrib.integrations.local_baserow.api.serializers import (
        LocalBaserowTableServiceFilterGroupSerializer,
        LocalBaserowTableServiceFilterSerializer,
    )

    if not isinstance(group, dict) or group.get("filter_type") not in ("AND", "OR"):
        raise ValidationError("Invalid filter group operator.")
    raw_filters = group.get("filters", [])
    if not isinstance(raw_filters, list):
        raise ValidationError("Expected a list of filters.")
    unavailable = get_unavailable_field_ids(raw_filters, service)
    indexes = [
        index
        for index, condition in enumerate(raw_filters)
        if not (isinstance(condition, dict) and condition.get("field") in unavailable)
    ]
    skipped = [
        raw_filters[index] for index in set(range(len(raw_filters))) - set(indexes)
    ]
    groups = LocalBaserowTableServiceFilterGroupSerializer(
        data=group.get("filter_groups", []), many=True
    )
    filters = LocalBaserowTableServiceFilterSerializer(
        data=[raw_filters[index] for index in indexes],
        many=True,
        context={
            "application_type": type(
                service.integration.application.specific.get_type()
            )
        },
    )
    groups.is_valid(raise_exception=True)
    filters.is_valid(raise_exception=True)
    pending = list(groups.validated_data)
    known = {None}
    ordered = []
    while pending:
        available = [g for g in pending if g["parent_group_id"] in known]
        if not available:
            raise ValidationError("Invalid or circular filter group ancestry.")
        for item in available:
            if item["id"] in known:
                raise ValidationError("Duplicate filter group.")
            known.add(item["id"])
            ordered.append(item)
            pending.remove(item)
    for condition in skipped:
        if condition.get("type") not in view_filter_type_registry.get_types():
            raise ValidationError("Unknown filter operator.")
        if condition.get("group") not in known:
            raise ValidationError("Unknown condition group.")
    for condition in filters.validated_data:
        field = condition["field"].specific
        if field.table_id != service.table_id or field.trashed:
            raise ValidationError(
                "A contributed filter field is incompatible with the source."
            )
        from baserow.core.exceptions import InstanceTypeDoesNotExist

        try:
            operator = view_filter_type_registry.get(condition["type"])
        except InstanceTypeDoesNotExist as exc:
            raise ValidationError("Unknown filter operator.") from exc
        if not operator.field_is_compatible(field):
            raise ValidationError("Incompatible filter operator.")
        if condition["group_id"] not in known:
            raise ValidationError("Unknown condition group.")
    return [
        {**condition, "index": index}
        for index, condition in zip(indexes, filters.validated_data)
    ], ordered


class RuntimeFilterGroupAdapter(LocalBaserowServiceGroupedFiltersAdapter):
    """Adapt validated transient groups to the standard nested filter builder."""

    def __init__(self, group, service, model, dispatch_context):
        from types import SimpleNamespace

        from rest_framework.exceptions import ValidationError

        super().__init__(service, model, dispatch_context)
        try:
            filters, groups = validate_runtime_filter_group(group, service)
        except ValidationError as exc:
            # The configuration was valid when saved, so it no longer matches the
            # source. Report it like the source's own invalid filters.
            raise ServiceImproperlyConfiguredDispatchException(
                "A dashboard filter condition no longer matches its source."
            ) from exc
        self._filter_type = group["filter_type"]
        self._filters = [
            SimpleNamespace(**{**f, "field_id": f["field"].id}) for f in filters
        ]
        self._groups = [SimpleNamespace(**g) for g in groups]

    def get_filter_values(self, value, view_filter_type):
        """
        Apply each selected value separately unless the operator combines lists
        itself: a row matches when it matches any selection, and negated operators
        exclude the rows matching any of them.
        """

        if (
            isinstance(value, list)
            and value
            and not view_filter_type.accepts_multiple_values
        ):
            return [view_filter_type.prepare_value(item) for item in value], (
                "AND" if view_filter_type.negated else "OR"
            )
        return super().get_filter_values(value, view_filter_type)

    @property
    def filter_type(self):
        return self._filter_type

    @property
    def filters(self):
        return self._filters

    @property
    def groups(self):
        return self._groups
