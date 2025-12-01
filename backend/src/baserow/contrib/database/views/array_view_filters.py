import zoneinfo
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta

from django.db.models import Q

from baserow.contrib.database.fields.field_filters import OptionallyAnnotatedQ
from baserow.contrib.database.fields.field_types import FormulaFieldType
from baserow.contrib.database.fields.filter_support.base import (
    HasAllValuesEqualFilterSupport,
    HasNumericValueComparableToFilterSupport,
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
    HasValueEmptyFilterSupport,
    HasValueEqualFilterSupport,
    HasValueLengthIsLowerThanFilterSupport,
    get_jsonb_has_date_value_filter_expr,
)
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.formula import (
    BaserowFormulaMultipleCollaboratorsType,
    BaserowFormulaNumberType,
    BaserowFormulaTextType,
)
from baserow.contrib.database.formula.expression_generator.django_expressions import (
    ComparisonOperator,
)
from baserow.contrib.database.formula.types.formula_types import (
    BaserowFormulaBooleanType,
    BaserowFormulaCharType,
    BaserowFormulaDateType,
    BaserowFormulaDurationType,
    BaserowFormulaMultipleSelectType,
    BaserowFormulaSingleSelectType,
    BaserowFormulaURLType,
)

from .registries import ViewFilterType
from .view_filters import BaseDateMultiStepViewFilterType, NotViewFilterTypeMixin


class HasEmptyValueViewFilterType(ViewFilterType):
    """
    The filter can be used to check for empty condition for
    items in an array.
    """

    type = "has_empty_value"
    compatible_field_types = [
        FormulaFieldType.compatible_with_formula_types(
            FormulaFieldType.array_of(BaserowFormulaTextType.type),
            FormulaFieldType.array_of(BaserowFormulaCharType.type),
            FormulaFieldType.array_of(BaserowFormulaURLType.type),
            FormulaFieldType.array_of(BaserowFormulaDateType.type),
            FormulaFieldType.array_of(BaserowFormulaSingleSelectType.type),
            FormulaFieldType.array_of(BaserowFormulaNumberType.type),
            FormulaFieldType.array_of(BaserowFormulaMultipleSelectType.type),
            FormulaFieldType.array_of(BaserowFormulaMultipleCollaboratorsType.type),
            FormulaFieldType.array_of(BaserowFormulaDurationType.type),
        ),
    ]

    def get_filter(self, field_name, value, model_field, field) -> OptionallyAnnotatedQ:
        field_type: HasValueEmptyFilterSupport = field_type_registry.get_by_model(field)
        return field_type.get_in_array_empty_query(field_name, model_field, field)


class HasNotEmptyValueViewFilterType(
    NotViewFilterTypeMixin, HasEmptyValueViewFilterType
):
    type = "has_not_empty_value"


class ComparisonHasValueFilter(ViewFilterType, ABC):
    """
    A filter that can be used to compare the values in an array with a specific value
    using a comparison operator.
    """

    def get_filter(
        self, field_name, value: str, model_field, field
    ) -> OptionallyAnnotatedQ:
        field_type = field_type_registry.get_by_model(field)
        try:
            filter_value = field_type.parse_filter_value(
                field, model_field, value.strip()
            )
        except ValueError:  # invalid filter value for the field
            return self.default_filter_on_exception()

        if filter_value is None:
            return Q()

        return self.get_filter_expression(field_name, filter_value, model_field, field)

    @abstractmethod
    def get_filter_expression(
        self, field_name, value, model_field, field
    ) -> OptionallyAnnotatedQ:
        """
        Return the filter expression to use for the required comparison.

        :param field_name: The name of the field to filter on.
        :param value: A non-empty string value to compare against.
        :param model_field: The model field instance.
        :param field: The field instance.
        :return: The filter expression to use.
        :raises ValidationError: If the value cannot be parsed to the proper type.
        """


class HasValueEqualViewFilterType(ComparisonHasValueFilter):
    """
    The filter can be used to check for "is" condition for
    items in an array.
    """

    type = "has_value_equal"
    compatible_field_types = [
        FormulaFieldType.compatible_with_formula_types(
            FormulaFieldType.array_of(BaserowFormulaTextType.type),
            FormulaFieldType.array_of(BaserowFormulaCharType.type),
            FormulaFieldType.array_of(BaserowFormulaURLType.type),
            FormulaFieldType.array_of(BaserowFormulaBooleanType.type),
            FormulaFieldType.array_of(BaserowFormulaSingleSelectType.type),
            FormulaFieldType.array_of(BaserowFormulaNumberType.type),
            FormulaFieldType.array_of(BaserowFormulaMultipleSelectType.type),
            FormulaFieldType.array_of(BaserowFormulaMultipleCollaboratorsType.type),
            FormulaFieldType.array_of(BaserowFormulaDurationType.type),
        ),
    ]

    def get_filter_expression(
        self, field_name, value, model_field, field
    ) -> OptionallyAnnotatedQ:
        field_type: HasValueEqualFilterSupport = field_type_registry.get_by_model(field)
        return field_type.get_in_array_is_query(field_name, value, model_field, field)


class HasNotValueEqualViewFilterType(
    NotViewFilterTypeMixin, HasValueEqualViewFilterType
):
    type = "has_not_value_equal"


class HasValueContainsViewFilterType(ViewFilterType):
    """
    The filter can be used to check for "contains" condition for
    items in an array.
    """

    type = "has_value_contains"
    compatible_field_types = [
        FormulaFieldType.compatible_with_formula_types(
            FormulaFieldType.array_of(BaserowFormulaTextType.type),
            FormulaFieldType.array_of(BaserowFormulaCharType.type),
            FormulaFieldType.array_of(BaserowFormulaURLType.type),
            FormulaFieldType.array_of(BaserowFormulaDateType.type),
            FormulaFieldType.array_of(BaserowFormulaSingleSelectType.type),
            FormulaFieldType.array_of(BaserowFormulaNumberType.type),
            FormulaFieldType.array_of(BaserowFormulaMultipleSelectType.type),
            FormulaFieldType.array_of(BaserowFormulaMultipleCollaboratorsType.type),
        ),
    ]

    def get_filter(self, field_name, value, model_field, field) -> OptionallyAnnotatedQ:
        field_type: HasValueContainsFilterSupport = field_type_registry.get_by_model(
            field
        )
        return field_type.get_in_array_contains_query(
            field_name, value, model_field, field
        )


class HasNotValueContainsViewFilterType(
    NotViewFilterTypeMixin, HasValueContainsViewFilterType
):
    type = "has_not_value_contains"


class HasValueContainsWordViewFilterType(ViewFilterType):
    """
    The filter can be used to check for "contains word" condition
    for items in an array.
    """

    type = "has_value_contains_word"
    compatible_field_types = [
        FormulaFieldType.compatible_with_formula_types(
            FormulaFieldType.array_of(BaserowFormulaTextType.type),
            FormulaFieldType.array_of(BaserowFormulaCharType.type),
            FormulaFieldType.array_of(BaserowFormulaURLType.type),
            FormulaFieldType.array_of(BaserowFormulaSingleSelectType.type),
            FormulaFieldType.array_of(BaserowFormulaMultipleSelectType.type),
            FormulaFieldType.array_of(BaserowFormulaMultipleCollaboratorsType.type),
        ),
    ]

    def get_filter(self, field_name, value, model_field, field) -> OptionallyAnnotatedQ:
        field_type: HasValueContainsWordFilterSupport = (
            field_type_registry.get_by_model(field)
        )
        return field_type.get_in_array_contains_word_query(
            field_name, value.strip(), model_field, field
        )


class HasNotValueContainsWordViewFilterType(
    NotViewFilterTypeMixin, HasValueContainsWordViewFilterType
):
    type = "has_not_value_contains_word"


class HasValueLengthIsLowerThanViewFilterType(ViewFilterType):
    """
    The filter can be used to check for "length is lower than" condition
    for items in an array.
    """

    type = "has_value_length_is_lower_than"
    compatible_field_types = [
        FormulaFieldType.compatible_with_formula_types(
            FormulaFieldType.array_of(BaserowFormulaTextType.type),
            FormulaFieldType.array_of(BaserowFormulaCharType.type),
            FormulaFieldType.array_of(BaserowFormulaURLType.type),
        ),
    ]

    def get_filter(self, field_name, value, model_field, field) -> OptionallyAnnotatedQ:
        value = value.strip()
        if value == "":
            return Q()

        try:
            # The value is expected to be an integer representing the length to compare
            filter_value = int(value)
        except (ValueError, TypeError):
            return self.default_filter_on_exception()

        field_type: HasValueLengthIsLowerThanFilterSupport = (
            field_type_registry.get_by_model(field)
        )
        return field_type.get_in_array_length_is_lower_than_query(
            field_name, filter_value, model_field, field
        )


class HasAllValuesEqualViewFilterType(ComparisonHasValueFilter):
    """
    The filter checks if all values in an array are equal to a specific value.
    """

    type = "has_all_values_equal"
    compatible_field_types = [
        FormulaFieldType.compatible_with_formula_types(
            FormulaFieldType.array_of(BaserowFormulaBooleanType.type)
        ),
    ]

    def get_filter_expression(
        self, field_name, value, model_field, field
    ) -> OptionallyAnnotatedQ:
        field_type: HasAllValuesEqualFilterSupport = field_type_registry.get_by_model(
            field
        )
        return field_type.get_has_all_values_equal_query(
            field_name, value, model_field, field
        )


# TODO: remove in future versions since it's the same as parent class now.
class HasAnySelectOptionEqualViewFilterType(HasValueEqualViewFilterType):
    """
    This filter can be used to verify if any of the select options in an array
    are equal to the option IDs provided.
    """

    type = "has_any_select_option_equal"
    compatible_field_types = [
        FormulaFieldType.compatible_with_formula_types(
            FormulaFieldType.array_of(BaserowFormulaSingleSelectType.type),
        ),
    ]


# TODO: remove in future versions since it's the same as parent class now.
class HasNoneSelectOptionEqualViewFilterType(
    NotViewFilterTypeMixin, HasAnySelectOptionEqualViewFilterType
):
    type = "has_none_select_option_equal"


class HasValueComparableToFilter(ComparisonHasValueFilter):
    type = "has_value_higher"
    compatible_field_types = [
        FormulaFieldType.compatible_with_formula_types(
            FormulaFieldType.array_of(BaserowFormulaNumberType.type),
            FormulaFieldType.array_of(BaserowFormulaDurationType.type),
        ),
    ]

    def get_filter_expression(self, field_name, value, model_field, field):
        field_type: HasNumericValueComparableToFilterSupport = (
            field_type_registry.get_by_model(field)
        )
        return field_type.get_has_numeric_value_comparable_to_filter_query(
            field_name, value, model_field, field, ComparisonOperator.HIGHER_THAN
        )


class HasNotValueHigherThanFilterType(
    NotViewFilterTypeMixin, HasValueComparableToFilter
):
    type = "has_not_value_higher"


class HasValueHigherOrEqualThanFilter(ComparisonHasValueFilter):
    type = "has_value_higher_or_equal"
    compatible_field_types = [
        FormulaFieldType.compatible_with_formula_types(
            FormulaFieldType.array_of(BaserowFormulaNumberType.type),
            FormulaFieldType.array_of(BaserowFormulaDurationType.type),
        ),
    ]

    def get_filter_expression(self, field_name, value, model_field, field):
        field_type: HasNumericValueComparableToFilterSupport = (
            field_type_registry.get_by_model(field)
        )
        return field_type.get_has_numeric_value_comparable_to_filter_query(
            field_name,
            value,
            model_field,
            field,
            ComparisonOperator.HIGHER_THAN_OR_EQUAL,
        )


class HasNotValueHigherOrEqualTHanFilterType(
    NotViewFilterTypeMixin, HasValueHigherOrEqualThanFilter
):
    type = "has_not_value_higher_or_equal"


class HasValueLowerThanFilter(ComparisonHasValueFilter):
    type = "has_value_lower"
    compatible_field_types = [
        FormulaFieldType.compatible_with_formula_types(
            FormulaFieldType.array_of(BaserowFormulaNumberType.type),
            FormulaFieldType.array_of(BaserowFormulaDurationType.type),
        ),
    ]

    def get_filter_expression(self, field_name, value, model_field, field):
        field_type: HasNumericValueComparableToFilterSupport = (
            field_type_registry.get_by_model(field)
        )
        return field_type.get_has_numeric_value_comparable_to_filter_query(
            field_name, value, model_field, field, ComparisonOperator.LOWER_THAN
        )


class HasNotValueLowerThanFilterType(NotViewFilterTypeMixin, HasValueLowerThanFilter):
    type = "has_not_value_lower"


class HasValueLowerOrEqualThanFilter(ComparisonHasValueFilter):
    type = "has_value_lower_or_equal"
    compatible_field_types = [
        FormulaFieldType.compatible_with_formula_types(
            FormulaFieldType.array_of(BaserowFormulaNumberType.type),
            FormulaFieldType.array_of(BaserowFormulaDurationType.type),
        ),
    ]

    def get_filter_expression(self, field_name, value, model_field, field):
        field_type: HasNumericValueComparableToFilterSupport = (
            field_type_registry.get_by_model(field)
        )
        return field_type.get_has_numeric_value_comparable_to_filter_query(
            field_name,
            value,
            model_field,
            field,
            ComparisonOperator.LOWER_THAN_OR_EQUAL,
        )


class HasNotValueLowerOrEqualTHanFilterType(
    NotViewFilterTypeMixin, HasValueLowerOrEqualThanFilter
):
    type = "has_not_value_lower_or_equal"


class ArrayDateMultiStepViewFilterType(BaseDateMultiStepViewFilterType):
    compatible_field_types = [
        FormulaFieldType.compatible_with_formula_types(
            FormulaFieldType.array_of(BaserowFormulaDateType.type)
        ),
    ]


class HasDateEqualViewFilterType(ArrayDateMultiStepViewFilterType):
    type = "has_date_equal"

    def get_filter_expression(
        self,
        field_name: str,
        model_field,
        lower_bound: date | datetime,
        upper_bound: date | datetime,
        timezone: zoneinfo.ZoneInfo,
    ) -> OptionallyAnnotatedQ:
        return get_jsonb_has_date_value_filter_expr(
            model_field, timezone, gte_of=lower_bound, lt_of=upper_bound
        )


class HasNotDateEqualViewFilterType(NotViewFilterTypeMixin, HasDateEqualViewFilterType):
    type = "has_not_date_equal"


class HasDateBeforeViewFilterType(ArrayDateMultiStepViewFilterType):
    type = "has_date_before"

    def get_filter_expression(
        self,
        field_name: str,
        model_field,
        lower_bound: date | datetime,
        upper_bound: date | datetime,
        timezone: zoneinfo.ZoneInfo,
    ) -> OptionallyAnnotatedQ:
        return get_jsonb_has_date_value_filter_expr(
            model_field, timezone, lt_of=lower_bound
        )


class HasNotDateBeforeViewFilterType(
    NotViewFilterTypeMixin, HasDateBeforeViewFilterType
):
    type = "has_not_date_before"


class HasDateOnOrBeforeViewFilterType(ArrayDateMultiStepViewFilterType):
    type = "has_date_on_or_before"

    def get_filter_expression(
        self,
        field_name: str,
        model_field,
        lower_bound: date | datetime,
        upper_bound: date | datetime,
        timezone: zoneinfo.ZoneInfo,
    ) -> OptionallyAnnotatedQ:
        return get_jsonb_has_date_value_filter_expr(
            model_field, timezone, lt_of=upper_bound
        )


class HasNotDateOnOrBeforeViewFilterType(
    NotViewFilterTypeMixin, HasDateOnOrBeforeViewFilterType
):
    type = "has_not_date_on_or_before"


class HasDateAfterViewFilterType(ArrayDateMultiStepViewFilterType):
    type = "has_date_after"

    def get_filter_expression(
        self,
        field_name: str,
        model_field,
        lower_bound: date | datetime,
        upper_bound: date | datetime,
        timezone: zoneinfo.ZoneInfo,
    ) -> OptionallyAnnotatedQ:
        return get_jsonb_has_date_value_filter_expr(
            model_field, timezone, gte_of=upper_bound
        )


class HasNotDateAfterViewFilterType(NotViewFilterTypeMixin, HasDateAfterViewFilterType):
    type = "has_not_date_after"


class HasDateOnOrAfterViewFilterType(ArrayDateMultiStepViewFilterType):
    type = "has_date_on_or_after"

    def get_filter_expression(
        self,
        field_name: str,
        model_field,
        lower_bound: date | datetime,
        upper_bound: date | datetime,
        timezone: zoneinfo.ZoneInfo,
    ) -> OptionallyAnnotatedQ:
        return get_jsonb_has_date_value_filter_expr(
            model_field, timezone, gte_of=lower_bound
        )


class HasNotDateOnOrAfterViewFilterType(
    NotViewFilterTypeMixin, HasDateOnOrAfterViewFilterType
):
    type = "has_not_date_on_or_after"


class HasDateWithinViewFilterType(ArrayDateMultiStepViewFilterType):
    type = "has_date_within"

    def get_filter_expression(
        self,
        field_name: str,
        model_field,
        lower_bound: date | datetime,
        upper_bound: date | datetime,
        timezone: zoneinfo.ZoneInfo,
    ) -> OptionallyAnnotatedQ:
        today = datetime.now(tz=timezone).date()
        if today < upper_bound:
            lower_bound = today
        else:
            upper_bound = today + timedelta(days=1)
        return get_jsonb_has_date_value_filter_expr(
            model_field,
            timezone,
            gte_of=lower_bound,
            lt_of=upper_bound,
        )


class HasNotDateWithinViewFilterType(
    NotViewFilterTypeMixin, HasDateWithinViewFilterType
):
    type = "has_not_date_within"
