from rest_framework import serializers

from baserow.contrib.dashboard.data_providers import (
    dashboard_filter_options_data_provider_type_registry,
)
from baserow.contrib.dashboard.filters.exceptions import InvalidDashboardFilterValues
from baserow.contrib.dashboard.filters.models import DashboardFilter
from baserow.contrib.dashboard.filters.operators import get_filter_operators
from baserow.contrib.dashboard.filters.values import (
    MAX_SELECTION_VALUES,
    validate_selection_budget,
)
from baserow.core.formula.serializers import FormulaSerializerField


class DashboardFilterSelectionField(serializers.ListField):
    def __init__(self, **kwargs):
        super().__init__(max_length=MAX_SELECTION_VALUES, **kwargs)

    def run_child_validation(self, data):
        if len(data) > MAX_SELECTION_VALUES:
            raise serializers.ValidationError(
                f"Select at most {MAX_SELECTION_VALUES} values in total.",
                code="max_selection_values",
            )
        # Match CharField's numeric coercion before applying the shared domain budget.
        values = [
            str(value)
            if isinstance(value, (int, float)) and not isinstance(value, bool)
            else value
            for value in data
        ]
        try:
            validate_selection_budget([values])
        except InvalidDashboardFilterValues as exc:
            raise serializers.ValidationError(str(exc), code=exc.code) from exc
        return super().run_child_validation(data)


class DashboardFilterSerializer(serializers.ModelSerializer):
    dashboard_id = serializers.IntegerField(read_only=True)
    values = DashboardFilterSelectionField(
        child=serializers.CharField(trim_whitespace=False, allow_blank=True),
        required=False,
    )
    formula_value = FormulaSerializerField(
        data_provider_type_registry=dashboard_filter_options_data_provider_type_registry
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["operator"] = serializers.ChoiceField(
            choices=list(get_filter_operators()), required=False
        )

    class Meta:
        model = DashboardFilter
        fields = (
            "id",
            "dashboard_id",
            "order",
            "label",
            "type",
            "operator",
            "mode",
            "multiple",
            "formula_value",
            "values",
        )
        read_only_fields = ("id", "dashboard_id", "order")


class OrderDashboardFiltersSerializer(serializers.Serializer):
    order = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        help_text="The IDs of the dashboard filters in their new order.",
    )
