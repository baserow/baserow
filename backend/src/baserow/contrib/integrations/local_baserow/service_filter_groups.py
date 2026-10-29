from typing import TYPE_CHECKING, Type, Union

from django.db.models import Q

from baserow.contrib.database.fields.field_filters import (
    AnnotatedQ,
    GroupedFiltersAdapter,
)
from baserow.contrib.database.views.registries import view_filter_type_registry
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.validator import ensure_string
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
            resolved_value = ensure_string(
                resolve_formula(
                    service_filter.value,
                    formula_runtime_function_registry,
                    self.dispatch_context,
                )
            )
        except Exception as exc:
            raise ServiceImproperlyConfiguredDispatchException(
                f"The {field_name} service filter formula can't be resolved: {exc}"
            ) from exc

        return view_filter_type.get_filter(
            field_name, resolved_value, model_field, field_object["field"]
        )


def validate_runtime_filter_group(group, service):
    """Validate a transient group's shape, ancestry, fields, operators and formulas."""
    from rest_framework.exceptions import ValidationError

    from baserow.contrib.integrations.local_baserow.api.serializers import (
        LocalBaserowTableServiceFilterGroupSerializer,
        LocalBaserowTableServiceFilterSerializer,
    )

    if not isinstance(group, dict) or group.get("filter_type") not in ("AND", "OR"):
        raise ValidationError("Invalid filter group operator.")
    groups = LocalBaserowTableServiceFilterGroupSerializer(
        data=group.get("filter_groups", []), many=True
    )
    filters = LocalBaserowTableServiceFilterSerializer(
        data=group.get("filters", []),
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
    return filters.validated_data, ordered


def build_runtime_filter(service, contributed_groups):
    """Combine stored and contributed groups into one independent service payload."""
    from baserow.contrib.integrations.local_baserow.api.serializers import (
        LocalBaserowTableServiceFilterGroupSerializer,
        LocalBaserowTableServiceFilterSerializer,
    )

    permanent = {
        "filter_type": service.filter_type,
        "filters": LocalBaserowTableServiceFilterSerializer(
            service.service_filters.all(), many=True
        ).data,
        "filter_groups": LocalBaserowTableServiceFilterGroupSerializer(
            service.service_filter_groups.all(), many=True
        ).data,
    }
    result = {"filter_type": service.filter_type, "filters": [], "filter_groups": []}
    for index, group in enumerate([permanent, *contributed_groups]):
        if not group.get("filters"):
            continue
        root_id = f"runtime-{index}"
        result["filter_groups"].append(
            {"id": root_id, "parent_group": None, "filter_type": group["filter_type"]}
        )
        for child in group.get("filter_groups", []):
            parent = child.get("parent_group")
            result["filter_groups"].append(
                {
                    **child,
                    "id": f"{root_id}:{child['id']}",
                    "parent_group": root_id
                    if parent is None
                    else f"{root_id}:{parent}",
                }
            )
        for condition in group["filters"]:
            parent = condition.get("group")
            result["filters"].append(
                {
                    **condition,
                    "group": root_id if parent is None else f"{root_id}:{parent}",
                }
            )
    return result


class RuntimeFilterGroupAdapter(LocalBaserowServiceGroupedFiltersAdapter):
    """Adapt validated transient groups to the standard nested filter builder."""

    def __init__(self, group, service, model, dispatch_context):
        from types import SimpleNamespace

        super().__init__(service, model, dispatch_context)
        filters, groups = validate_runtime_filter_group(group, service)
        self._filter_type = group["filter_type"]
        self._filters = [
            SimpleNamespace(**{**f, "field_id": f["field"].id}) for f in filters
        ]
        self._groups = [SimpleNamespace(**g) for g in groups]

    @property
    def filter_type(self):
        return self._filter_type

    @property
    def filters(self):
        return self._filters

    @property
    def groups(self):
        return self._groups
