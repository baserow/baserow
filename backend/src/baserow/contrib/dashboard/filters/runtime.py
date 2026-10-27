from django.db.models import Q

from baserow.contrib.dashboard.data_providers import DashboardFilterDataProviderType
from baserow.contrib.dashboard.formula_references import get_direct_reference_path
from baserow.contrib.database.fields.field_filters import AnnotatedQ, FilterBuilder
from baserow.contrib.database.views.view_filters import (
    BaseDateMultiStepViewFilterType,
    NotViewFilterTypeMixin,
)
from baserow.core.formula.validator import ensure_string
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)

from .operators import get_filter_operators


def get_dashboard_filter_path(formula):
    """Only direct references inherit the control's operator.

    Calculated expressions keep their own source condition: an expression can
    combine several controls, whose operators need not agree.
    """

    return get_direct_reference_path(formula, DashboardFilterDataProviderType())


def get_dashboard_filter_q(service_filter, model, context):
    path = get_dashboard_filter_path(service_filter.value)
    if path is None:
        return None

    provider = DashboardFilterDataProviderType()
    configuration = provider.get_configuration(context, path[0])
    if configuration is None:
        return Q()
    value = provider.get_data_chunk(context, path)
    values = value if isinstance(value, list) else [value]
    values = [ensure_string(value) for value in values if value is not None]
    # Resolve indexed references before deduplicating: submitted positions are part
    # of the provider contract, but repeating a resolved predicate changes nothing.
    values = list(dict.fromkeys(value for value in values if value.strip()))
    if not values:
        return Q()

    field_object = model._field_objects[service_filter.field_id]
    operator = get_filter_operators(configuration.type).get(configuration.operator)
    if operator is None or not operator.field_is_compatible(field_object["field"]):
        raise ServiceImproperlyConfiguredDispatchException(
            "The dashboard filter operator is not compatible with this field."
        )

    # Positive operators accept any selected value; negative ones exclude all.
    builder = FilterBuilder(
        filter_type="AND" if isinstance(operator, NotViewFilterTypeMixin) else "OR"
    )
    name = field_object["name"]
    for value in values:
        if isinstance(operator, BaseDateMultiStepViewFilterType) and "?" not in value:
            # Table-backed dropdowns expose ISO dates. The Builder date editor
            # already supplies its timezone, value and relative-date operation.
            timezone = field_object["field"].date_force_timezone or "UTC"
            value = f"{timezone}?{value}?exact_date"
        builder.filter(
            operator.get_filter(
                name, value, model._meta.get_field(name), field_object["field"]
            )
        )
    query, annotations = builder.get_filters_and_annotations()
    return AnnotatedQ(annotations, query)
