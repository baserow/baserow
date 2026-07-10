from typing import TYPE_CHECKING, Type, Union

from django.db.models import Q

from baserow.contrib.database.fields.field_filters import (
    AnnotatedQ,
    GroupedFiltersAdapter,
)
from baserow.contrib.database.views.registries import view_filter_type_registry
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW
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

        # We need this test for compatibility purposes with old values.
        if (
            service_filter.value_is_formula
            or service_filter.value["mode"] == BASEROW_FORMULA_MODE_RAW
        ):
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
                    f"The {field_name} service filter formula can't be "
                    "resolved: {exc}"
                ) from exc
        else:
            resolved_value = service_filter.value["formula"]

        return view_filter_type.get_filter(
            field_name, resolved_value, model_field, field_object["field"]
        )
