from baserow.contrib.database.fields.field_filters import OptionallyAnnotatedQ
from baserow.contrib.database.fields.field_types import FormulaFieldType
from baserow.contrib.database.fields.filter_support.base import (
    HasAllValuesEqualFilterSupport,
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
    HasValueEmptyFilterSupport,
    HasValueFilterSupport,
    HasValueLengthIsLowerThanFilterSupport,
)
from baserow.contrib.database.fields.filter_support.exceptions import (
    FilterNotSupportedException,
)
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.formula import BaserowFormulaTextType
from baserow.contrib.database.formula.types.formula_types import (
    BaserowFormulaBooleanType,
    BaserowFormulaCharType,
    BaserowFormulaSingleSelectType,
    BaserowFormulaURLType,
)

from .registries import ViewFilterType
from .view_filters import NotViewFilterTypeMixin


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
            FormulaFieldType.array_of(BaserowFormulaSingleSelectType.type),
        ),
    ]

    def get_filter(self, field_name, value, model_field, field) -> OptionallyAnnotatedQ:
        field_type = field_type_registry.get_by_model(field)
        try:
            if not isinstance(field_type, HasValueEmptyFilterSupport):
                raise FilterNotSupportedException(field_type)

            return field_type.get_in_array_empty_query(field_name, model_field, field)
        except FilterNotSupportedException:
            return self.default_filter_on_exception()


class HasNotEmptyValueViewFilterType(
    NotViewFilterTypeMixin, HasEmptyValueViewFilterType
):
    type = "has_not_empty_value"


class HasValueEqualViewFilterType(ViewFilterType):
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
        ),
    ]

    def get_filter(self, field_name, value, model_field, field) -> OptionallyAnnotatedQ:
        field_type = field_type_registry.get_by_model(field)
        try:
            if not isinstance(field_type, HasValueFilterSupport):
                raise FilterNotSupportedException(field_type)
            return field_type.get_in_array_is_query(
                field_name, value, model_field, field
            )
        except FilterNotSupportedException:
            return self.default_filter_on_exception()


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
            FormulaFieldType.array_of(BaserowFormulaSingleSelectType.type),
        ),
    ]

    def get_filter(self, field_name, value, model_field, field) -> OptionallyAnnotatedQ:
        field_type = field_type_registry.get_by_model(field)
        try:
            if not isinstance(field_type, HasValueContainsFilterSupport):
                raise FilterNotSupportedException(field_type)

            return field_type.get_in_array_contains_query(
                field_name, value, model_field, field
            )
        except FilterNotSupportedException:
            return self.default_filter_on_exception()


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
        ),
    ]

    def get_filter(self, field_name, value, model_field, field) -> OptionallyAnnotatedQ:
        field_type = field_type_registry.get_by_model(field)
        try:
            if not isinstance(field_type, HasValueContainsWordFilterSupport):
                raise FilterNotSupportedException(field_type)

            return field_type.get_in_array_contains_word_query(
                field_name, value, model_field, field
            )
        except FilterNotSupportedException:
            return self.default_filter_on_exception()


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
        field_type = field_type_registry.get_by_model(field)
        try:
            if not isinstance(field_type, HasValueLengthIsLowerThanFilterSupport):
                raise FilterNotSupportedException(field_type)

            return field_type.get_in_array_length_is_lower_than_query(
                field_name, value, model_field, field
            )
        except FilterNotSupportedException:
            return self.default_filter_on_exception()


class HasAllValuesEqualViewFilterType(ViewFilterType):
    """
    The filter checks if all values in an array are equal to a specific value.
    """

    type = "has_all_values_equal"
    compatible_field_types = [
        FormulaFieldType.compatible_with_formula_types(
            FormulaFieldType.array_of(BaserowFormulaBooleanType.type)
        ),
    ]

    def get_filter(self, field_name, value, model_field, field) -> OptionallyAnnotatedQ:
        try:
            field_type = field_type_registry.get_by_model(field)
            if not isinstance(field_type, HasAllValuesEqualFilterSupport):
                raise FilterNotSupportedException(field_type)
            return field_type.get_has_all_values_equal_query(
                field_name, value, model_field, field
            )
        except FilterNotSupportedException:
            return self.default_filter_on_exception()


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

    def get_filter(self, field_name, value, model_field, field) -> OptionallyAnnotatedQ:
        return super().get_filter(field_name, value.split(","), model_field, field)


class HasNoneSelectOptionEqualViewFilterType(
    NotViewFilterTypeMixin, HasAnySelectOptionEqualViewFilterType
):
    """
    This filter can be used to verify if none of the select options in an array are
    equal to the option IDs provided
    """

    type = "has_none_select_option_equal"
