import re
from abc import ABC
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, List, Optional, Set, Type, Union

from django.contrib.postgres.fields import ArrayField, JSONField
from django.db import models
from django.db.models import Expression, F
from django.db.models import Field as DjangoField
from django.db.models import Func, Q, QuerySet, TextField, Value
from django.db.models.functions import Cast, Concat

from dateutil import parser
from rest_framework import serializers
from rest_framework.fields import Field

from baserow.contrib.database.fields.expressions import (
    extract_jsonb_array_values_to_single_string,
    extract_jsonb_list_values_to_array,
    json_extract_path,
)
from baserow.contrib.database.fields.field_filters import (
    AnnotatedQ,
    OptionallyAnnotatedQ,
)
from baserow.contrib.database.fields.field_sortings import OptionallyAnnotatedOrderBy
from baserow.contrib.database.fields.filter_support.base import (
    HasAllValuesEqualFilterSupport,
    HasNumericValueComparableToFilterSupport,
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
    HasValueEmptyFilterSupport,
    HasValueEqualFilterSupport,
    HasValueLengthIsLowerThanFilterSupport,
    get_array_json_filter_expression,
    get_jsonb_contains_filter_expr,
    get_jsonb_contains_word_filter_expr,
)
from baserow.contrib.database.fields.filter_support.multiple_select import (
    MultipleSelectFormulaTypeFilterSupport,
    get_jsonb_has_any_in_value_filter_expr,
)
from baserow.contrib.database.fields.filter_support.single_select import (
    SingleSelectFormulaTypeFilterSupport,
)
from baserow.contrib.database.fields.mixins import get_date_time_format
from baserow.contrib.database.fields.utils.duration import (
    D_H_M_S,
    postgres_interval_to_seconds,
)
from baserow.contrib.database.formula.ast.tree import (
    BaserowBooleanLiteral,
    BaserowDecimalLiteral,
    BaserowExpression,
    BaserowFieldReference,
    BaserowFunctionCall,
    BaserowIntegerLiteral,
    BaserowStringLiteral,
)
from baserow.contrib.database.formula.expression_generator.django_expressions import (
    ComparisonOperator,
    JSONArrayCompareIntervalValueExpr,
    JSONArrayCompareNumericValueExpr,
)
from baserow.contrib.database.formula.registries import formula_function_registry
from baserow.contrib.database.formula.types.exceptions import UnknownFormulaType
from baserow.contrib.database.formula.types.filter_support import (
    BaserowFormulaArrayFilterSupportMixin,
)
from baserow.contrib.database.formula.types.formula_type import (
    BaserowFormulaInvalidType,
    BaserowFormulaType,
    BaserowFormulaTypeHasEmptyBaserowExpression,
    BaserowFormulaValidType,
    UnTyped,
)
from baserow.core.db import collate_expression
from baserow.core.storage import get_default_storage
from baserow.core.utils import list_to_comma_separated_string


class BaserowJSONBObjectBaseType(BaserowFormulaValidType, ABC):
    def parse_filter_value(self, field, model_field, value):
        """
        Since the subclasses don't have a baserow_field_type or data might be stored
        differently due to the JSONB nature, return the value as is here and let the
        filter method handle it.
        """

        from baserow.contrib.database.fields.registries import field_type_registry

        if self.baserow_field_type is None:
            return value if value != "" else None

        return field_type_registry.get(self.baserow_field_type).parse_filter_value(
            field, model_field, value
        )


class BaserowFormulaBaseTextType(BaserowFormulaTypeHasEmptyBaserowExpression):
    can_group_by = True

    @property
    def comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [
            BaserowFormulaTextType,
            BaserowFormulaDateType,
            BaserowFormulaNumberType,
            BaserowFormulaBooleanType,
            BaserowFormulaCharType,
            BaserowFormulaLinkType,
        ]

    @property
    def limit_comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        # Force users to explicitly convert to text before doing any limit comparison
        # operators as lexicographical comparison can be surprising and so should be opt
        # in
        return [BaserowFormulaTextType, BaserowFormulaCharType, BaserowFormulaLinkType]

    @property
    def addable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [BaserowFormulaTextType, BaserowFormulaCharType, BaserowFormulaLinkType]

    def add(
        self,
        add_func_call: "BaserowFunctionCall[UnTyped]",
        arg1: "BaserowExpression[BaserowFormulaTextType]",
        arg2: "BaserowExpression[BaserowFormulaTextType]",
    ):
        return formula_function_registry.get("concat").call_and_type_with_args(
            [arg1, arg2]
        )

    def placeholder_empty_value(self):
        return Value("", output_field=models.TextField())

    def placeholder_empty_baserow_expression(
        self,
    ) -> "BaserowExpression[BaserowFormulaValidType]":
        return literal("")

    def _get_order_field_expression(self, field_name: str) -> Expression | F:
        return collate_expression(F(field_name))


class BaserowFormulaTextType(
    HasValueEmptyFilterSupport,
    HasValueEqualFilterSupport,
    HasValueContainsFilterSupport,
    HasValueContainsWordFilterSupport,
    HasValueLengthIsLowerThanFilterSupport,
    BaserowFormulaBaseTextType,
    BaserowFormulaTypeHasEmptyBaserowExpression,
    BaserowFormulaValidType,
):
    type = "text"
    baserow_field_type = "text"
    can_order_by_in_array = True
    can_have_db_index = True

    def __init__(self, *args, **kwargs):
        unwrap_cast_to_text = kwargs.pop("unwrap_cast_to_text", True)
        self.unwrap_cast_to_text = unwrap_cast_to_text
        super().__init__(*args, **kwargs)

    def cast_to_text(
        self,
        to_text_func_call: "BaserowFunctionCall[UnTyped]",
        arg: "BaserowExpression[BaserowFormulaValidType]",
    ) -> "BaserowExpression[BaserowFormulaType]":
        if self.unwrap_cast_to_text:
            # Explicitly unwrap the func_call here and just return the arg as it is
            # already in the text type and we don't want to return to_text(arg) but
            # instead just arg.
            return arg
        else:
            # In some cases, we're using the `text` formula type for types that are
            # not necessarily already in the text format. In that case, we do want to
            # cast it to the text type. This is for example the case with the UUID
            # field type.
            return super().cast_to_text(to_text_func_call, arg)

    def get_order_by_in_array_expr(self, field, field_name, order_direction):
        return collate_expression(
            JSONBSingleKeyArrayExpression(
                field_name, "value", "text", output_field=models.TextField()
            )
        )

    def get_in_array_empty_value(self, field: "Field") -> Any:
        return [None, ""]


class BaserowFormulaURLType(BaserowFormulaTextType, BaserowFormulaValidType):
    type = "url"
    baserow_field_type = "url"


class BaserowFormulaCharType(BaserowFormulaTextType, BaserowFormulaValidType):
    type = "char"
    baserow_field_type = "text"
    can_order_by_in_array = True
    can_group_by = True

    def get_order_by_in_array_expr(self, field, field_name, order_direction):
        return collate_expression(
            JSONBSingleKeyArrayExpression(
                field_name, "value", "text", output_field=models.TextField()
            )
        )

    def placeholder_empty_baserow_expression(
        self,
    ) -> "BaserowExpression[BaserowFormulaValidType]":
        return formula_function_registry.get("tovarchar")(literal(""))


class BaserowFormulaLinkType(BaserowJSONBObjectBaseType):
    type = "link"
    baserow_field_type = None
    can_order_by = False
    can_group_by = False

    @property
    def comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [
            type(self),
        ]

    @property
    def limit_comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return []

    @property
    def addable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return []

    @property
    def subtractable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return []

    def cast_to_text(
        self,
        to_text_func_call: "BaserowFunctionCall[UnTyped]",
        arg: "BaserowExpression[BaserowFormulaValidType]",
    ) -> "BaserowExpression[BaserowFormulaType]":
        return formula_function_registry.get("get_link_label")(arg)

    def get_baserow_field_instance_and_type(self):
        return self, self

    @property
    def db_column_fields(self) -> Set[str]:
        return {}

    def get_model_field(self, instance, **kwargs) -> models.Field:
        kwargs["null"] = True
        kwargs["blank"] = True

        return JSONField(default=dict, **kwargs)

    def get_response_serializer_field(self, instance, **kwargs) -> Optional[Field]:
        return self.get_serializer_field(instance, **kwargs)

    def get_serializer_field(self, instance, **kwargs) -> Optional[Field]:
        required = kwargs.get("required", False)

        from baserow.contrib.database.formula.types.serializers import LinkSerializer

        return LinkSerializer(
            **{"required": required, "allow_null": not required, **kwargs}
        )

    def get_export_value(self, value, field_object, rich_value=False) -> Any:
        if rich_value:
            return value
        elif value is not None:
            if "label" in value:
                return f"{value['label']} ({value['url']})"
            else:
                return f"{value['url']}"
        else:
            return ""

    def contains_query(self, field_name, value, model_field, field):
        value = value.strip()
        # If an empty value has been provided we do not want to filter at all.
        if value == "":
            return Q()
        return Q(**{f"{field_name}__url__icontains": value}) | Q(
            **{f"{field_name}__label__icontains": value}
        )

    def get_alter_column_prepare_old_value(self, connection, from_field, to_field):
        sql = f"""
            p_in = p_in->'label' + ' (' + p_in->'url' + ')';
        """
        return sql, {}

    def get_human_readable_value(self, value: Any, field_object) -> str:
        human_readable_value = self.get_export_value(
            value, field_object, rich_value=False
        )
        if human_readable_value is None:
            return ""
        else:
            return str(human_readable_value)

    def placeholder_empty_value(self):
        return Value({}, output_field=JSONField())

    def placeholder_empty_baserow_expression(
        self,
    ) -> "BaserowExpression[BaserowFormulaValidType]":
        return formula_function_registry.get("link")(literal(""))

    def get_search_expression(self, field, queryset):
        return Concat(
            json_extract_path(F(field.db_column), [Value("label")]),
            Value(" ("),
            json_extract_path(F(field.db_column), [Value("url")]),
            Value(")"),
            output_field=models.TextField(),
        )

    def get_search_expression_in_array(self, field, queryset):
        def transform_value_to_text_func(x):
            # Make sure we don't send the keys of the jsonb to ts_vector by extracting
            # and re-ordering the label/url parameters to match the correct format
            return Func(
                x,
                Value('.*"url".*:.*"([^"]+)".*"label".*:.*"([^"]+)".*'),
                Value("\\2 (\\1)"),
                Value("g", output_field=models.TextField()),
                function="regexp_replace",
                output_field=models.TextField(),
            )

        return extract_jsonb_array_values_to_single_string(
            field,
            queryset,
            transform_value_to_text_func=transform_value_to_text_func,
        )

    def is_searchable(self, field):
        return True


class BaserowFormulaButtonType(BaserowFormulaLinkType):
    type = "button"


class BaserowFormulaNumberType(
    HasValueEmptyFilterSupport,
    HasValueEqualFilterSupport,
    HasValueContainsFilterSupport,
    HasNumericValueComparableToFilterSupport,
    BaserowFormulaTypeHasEmptyBaserowExpression,
    BaserowFormulaValidType,
):
    type = "number"
    baserow_field_type = "number"
    user_overridable_formatting_option_fields = [
        "number_decimal_places",
        "number_prefix",
        "number_suffix",
        "number_separator",
    ]
    MAX_DIGITS = 50
    can_order_by_in_array = True
    can_group_by = True
    can_have_db_index = True

    def __init__(
        self,
        number_decimal_places: int,
        number_prefix: str = "",
        number_suffix: str = "",
        number_separator: str = "",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.number_decimal_places = number_decimal_places
        self.number_prefix = number_prefix
        self.number_suffix = number_suffix
        self.number_separator = number_separator

    @property
    def comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [
            type(self),
            BaserowFormulaTextType,
        ]

    @property
    def limit_comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [type(self)]

    @property
    def addable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [type(self)]

    @property
    def subtractable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [type(self)]

    @property
    def multipliable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [type(self), BaserowFormulaDurationType]

    @property
    def dividable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [type(self)]

    def add(
        self,
        add_func_call: "BaserowFunctionCall[UnTyped]",
        arg1: "BaserowExpression[BaserowFormulaNumberType]",
        arg2: "BaserowExpression[BaserowFormulaNumberType]",
    ):
        return add_func_call.with_valid_type(
            calculate_number_type([arg1.expression_type, arg2.expression_type])
        )

    def minus(
        self,
        minus_func_call: "BaserowFunctionCall[UnTyped]",
        arg1: "BaserowExpression[BaserowFormulaNumberType]",
        arg2: "BaserowExpression[BaserowFormulaNumberType]",
    ):
        return minus_func_call.with_valid_type(
            calculate_number_type([arg1.expression_type, arg2.expression_type])
        )

    def multiply(
        self,
        multiply_func_call: "BaserowFunctionCall[UnTyped]",
        arg1: "BaserowExpression[BaserowFormulaNumberType]",
        arg2: "BaserowExpression[BaserowFormulaNumberType]",
    ):
        if isinstance(arg2.expression_type, BaserowFormulaDurationType):
            return multiply_func_call.with_valid_type(arg2.expression_type)
        else:
            return multiply_func_call.with_valid_type(
                calculate_number_type([arg1.expression_type, arg2.expression_type])
            )

    def divide(
        self,
        divide_func_call: "BaserowFunctionCall[UnTyped]",
        arg1: "BaserowExpression[BaserowFormulaNumberType]",
        arg2: "BaserowExpression[BaserowFormulaNumberType]",
    ):
        from baserow.contrib.database.fields.models import NUMBER_MAX_DECIMAL_PLACES

        return divide_func_call.with_valid_type(
            BaserowFormulaNumberType(NUMBER_MAX_DECIMAL_PLACES)
        )

    def should_recreate_when_old_type_was(self, old_type: "BaserowFormulaType") -> bool:
        if isinstance(old_type, BaserowFormulaNumberType):
            return self.number_decimal_places != old_type.number_decimal_places
        else:
            return True

    def wrap_at_field_level(self, expr: "BaserowExpression[BaserowFormulaType]"):
        return formula_function_registry.get("error_to_nan")(expr)

    def unwrap_at_field_level(self, expr: "BaserowFunctionCall[BaserowFormulaType]"):
        return expr.args[0].with_valid_type(expr.expression_type)

    def placeholder_empty_value(self):
        return Value(
            0, output_field=models.DecimalField(max_digits=50, decimal_places=0)
        )

    def placeholder_empty_baserow_expression(
        self,
    ) -> "BaserowExpression[BaserowFormulaValidType]":
        return literal(0)

    def get_order_by_in_array_expr(self, field, field_name, order_direction):
        return JSONBSingleKeyArrayExpression(
            field_name,
            "value",
            "numeric",
            output_field=ArrayField(
                base_field=models.DecimalField(max_digits=50, decimal_places=0)
            ),
        )

    def get_in_array_empty_value(self, field: "Field") -> Any:
        return None

    def get_in_array_is_query(
        self, field_name: str, value: str, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        return get_array_json_filter_expression(
            JSONArrayCompareNumericValueExpr,
            field_name,
            Value(value),
            comparison_op=ComparisonOperator.EQUAL,
        )

    def __str__(self) -> str:
        return f"number({self.number_decimal_places})"


class BaserowFormulaBooleanType(
    HasValueEmptyFilterSupport,
    HasAllValuesEqualFilterSupport,
    HasValueEqualFilterSupport,
    BaserowFormulaTypeHasEmptyBaserowExpression,
    BaserowFormulaValidType,
):
    type = "boolean"
    baserow_field_type = "boolean"
    can_order_by_in_array = True
    can_group_by = True
    can_have_db_index = True

    def get_in_array_empty_value(self, field: "Field") -> Any:
        return None

    @property
    def comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [
            type(self),
            BaserowFormulaTextType,
        ]

    @property
    def limit_comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        # true > true makes no sense
        return []

    def placeholder_empty_value(self):
        return Value(False, output_field=models.BooleanField())

    def placeholder_empty_baserow_expression(
        self,
    ) -> "BaserowExpression[BaserowFormulaValidType]":
        return literal(False)

    def try_coerce_to_not_null(
        self, expr: "BaserowExpression[BaserowFormulaValidType]"
    ):
        return expr

    def get_in_array_is_query(
        self, field_name: str, value: bool, model_field: models.Field, field: "Field"
    ) -> OptionallyAnnotatedQ:
        return get_jsonb_has_any_in_value_filter_expr(
            model_field, [str(value).lower()], query_path="$[*].value"
        )

    def get_order_by_in_array_expr(self, field, field_name, order_direction):
        return JSONBSingleKeyArrayExpression(
            field_name,
            "value",
            "boolean",
            output_field=ArrayField(
                base_field=models.DecimalField(max_digits=50, decimal_places=0)
            ),
        )


def _calculate_addition_interval_type(
    arg1: BaserowExpression[BaserowFormulaValidType],
    arg2: BaserowExpression[BaserowFormulaValidType],
) -> BaserowFormulaValidType:
    arg1_type = arg1.expression_type
    arg2_type = arg2.expression_type
    if isinstance(arg1_type, BaserowFormulaDateIntervalTypeMixin) and isinstance(
        arg2_type, BaserowFormulaDateIntervalTypeMixin
    ):
        # interval + interval = interval
        resulting_type = arg1_type
    elif isinstance(arg1_type, BaserowFormulaDateIntervalTypeMixin):
        # interval + date = date
        resulting_type = arg2_type
    else:
        # date + interval = date
        resulting_type = arg1_type
    resulting_type.nullable = arg1_type.nullable or arg2_type.nullable
    return resulting_type


class BaserowFormulaDateIntervalTypeMixin:
    """
    Empty mixin to allow us to check if a type is a date interval type or a duration
    type. NOTE: This can be removed once the BaserowFormulaDateIntervalType is removed.
    """


# Deprecated, use BaserowFormulaDurationType instead
class BaserowFormulaDateIntervalType(
    BaserowFormulaTypeHasEmptyBaserowExpression,
    BaserowFormulaValidType,
    BaserowFormulaDateIntervalTypeMixin,
):
    type = "date_interval"
    baserow_field_type = None
    can_group_by = True

    @property
    def comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [type(self)]

    @property
    def limit_comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [type(self)]

    @property
    def addable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [type(self), BaserowFormulaDateType]

    @property
    def subtractable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [type(self)]

    def add(
        self,
        add_func_call: "BaserowFunctionCall[UnTyped]",
        arg1: "BaserowExpression[BaserowFormulaValidType]",
        arg2: "BaserowExpression[BaserowFormulaValidType]",
    ):
        return add_func_call.with_valid_type(
            _calculate_addition_interval_type(arg1, arg2)
        )

    def minus(
        self,
        minus_func_call: "BaserowFunctionCall[UnTyped]",
        arg1: "BaserowExpression[BaserowFormulaValidType]",
        arg2: "BaserowExpression[BaserowFormulaValidType]",
    ):
        return minus_func_call.with_valid_type(
            BaserowFormulaDateIntervalType(
                nullable=arg1.expression_type.nullable or arg2.expression_type.nullable
            )
        )

    def get_baserow_field_instance_and_type(self):
        # Until Baserow has a duration field type implement the required methods below
        return self, self

    @property
    def db_column_fields(self) -> Set[str]:
        return {}

    def get_model_field(self, instance, **kwargs) -> models.Field:
        from baserow.contrib.database.fields.fields import (
            DurationFieldUsingPostgresFormatting,
        )

        kwargs["null"] = True
        kwargs["blank"] = True

        return DurationFieldUsingPostgresFormatting(**kwargs)

    def get_response_serializer_field(self, instance, **kwargs) -> Optional[Field]:
        return self.get_serializer_field(instance, **kwargs)

    def get_serializer_field(self, instance, **kwargs) -> Optional[Field]:
        required = kwargs.get("required", False)

        return serializers.CharField(
            **{"required": required, "allow_null": not required, **kwargs}
        )

    def get_export_value(self, value, field_object, rich_value=False) -> Any:
        if rich_value:
            return value
        else:
            return value if value is not None else ""

    def contains_query(self, field_name, value, model_field, field):
        return Q()

    def get_alter_column_prepare_old_value(self, connection, from_field, to_field):
        return None

    def get_human_readable_value(self, value: Any, field_object) -> str:
        human_readable_value = self.get_export_value(
            value, field_object, rich_value=False
        )
        if human_readable_value is None:
            return ""
        else:
            return str(human_readable_value)

    def placeholder_empty_value(self):
        return Value(timedelta(hours=0), output_field=models.DurationField())

    def placeholder_empty_baserow_expression(
        self,
    ) -> "BaserowExpression[BaserowFormulaValidType]":
        func = formula_function_registry.get("date_interval")
        return func(literal("0 hours"))

    def is_searchable(self, field):
        return True

    def get_search_expression(self, field: Field, queryset: QuerySet) -> Expression:
        return Cast(field.db_column, output_field=models.TextField())


class BaserowFormulaDurationType(
    BaserowFormulaTypeHasEmptyBaserowExpression,
    BaserowFormulaValidType,
    BaserowFormulaDateIntervalTypeMixin,
    HasValueEmptyFilterSupport,
):
    type = "duration"
    baserow_field_type = "duration"
    user_overridable_formatting_option_fields = ["duration_format"]
    can_group_by = True
    can_order_by_in_array = True

    def __init__(self, duration_format: str = D_H_M_S, **kwargs):
        super().__init__(**kwargs)
        self.duration_format = duration_format

    def get_in_array_empty_value(self, field: "Field") -> Any:
        return None

    @property
    def comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [type(self)]

    @property
    def limit_comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [type(self)]

    @property
    def addable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [type(self), BaserowFormulaDateType]

    @property
    def multipliable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [BaserowFormulaNumberType]

    @property
    def subtractable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [type(self)]

    @property
    def dividable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [BaserowFormulaNumberType]

    def add(
        self,
        add_func_call: "BaserowFunctionCall[UnTyped]",
        arg1: "BaserowExpression[BaserowFormulaValidType]",
        arg2: "BaserowExpression[BaserowFormulaValidType]",
    ):
        return add_func_call.with_valid_type(
            _calculate_addition_interval_type(arg1, arg2)
        )

    def minus(
        self,
        minus_func_call: "BaserowFunctionCall[UnTyped]",
        arg1: "BaserowExpression[BaserowFormulaValidType]",
        arg2: "BaserowExpression[BaserowFormulaValidType]",
    ):
        return minus_func_call.with_valid_type(
            BaserowFormulaDurationType(
                duration_format=self.duration_format,
                nullable=arg1.expression_type.nullable or arg2.expression_type.nullable,
            )
        )

    def multiply(
        self,
        multiply_func_call: "BaserowFunctionCall[UnTyped]",
        arg1: "BaserowExpression[BaserowFormulaNumberType]",
        arg2: "BaserowExpression[BaserowFormulaNumberType]",
    ):
        return multiply_func_call.with_valid_type(
            BaserowFormulaDurationType(
                duration_format=self.duration_format,
                nullable=arg1.expression_type.nullable or arg2.expression_type.nullable,
            )
        )

    def divide(
        self,
        multiply_func_call: "BaserowFunctionCall[UnTyped]",
        arg1: "BaserowExpression[BaserowFormulaNumberType]",
        arg2: "BaserowExpression[BaserowFormulaNumberType]",
    ):
        return multiply_func_call.with_valid_type(
            BaserowFormulaDurationType(
                duration_format=self.duration_format,
                nullable=arg1.expression_type.nullable or arg2.expression_type.nullable,
            )
        )

    def placeholder_empty_value(self):
        return Value(timedelta(hours=0), output_field=models.DurationField())

    def placeholder_empty_baserow_expression(
        self,
    ) -> "BaserowExpression[BaserowFormulaValidType]":
        func = formula_function_registry.get("date_interval")
        return func(literal("0 hours"))

    def get_order_by_in_array_expr(self, field, field_name, order_direction):
        return JSONBSingleKeyArrayExpression(
            field_name, "value", "interval", output_field=models.DurationField()
        )

    def get_has_numeric_value_comparable_to_filter_query(
        self,
        field_name: str,
        value: str,
        model_field: models.Field,
        field: "Field",
        comparison_op: ComparisonOperator,
    ) -> "OptionallyAnnotatedQ":
        try:
            value = int(value)
        except (TypeError, ValueError):
            return Q()

        return get_array_json_filter_expression(
            JSONArrayCompareIntervalValueExpr,
            field_name,
            Value(value),
            comparison_op=comparison_op,
        )

    def get_in_array_is_query(self, field_name, value, model_field, field):
        return self.get_has_numeric_value_comparable_to_filter_query(
            field_name, value, model_field, field, ComparisonOperator.EQUAL
        )


class BaserowFormulaDateType(
    HasValueEmptyFilterSupport, HasValueContainsFilterSupport, BaserowFormulaValidType
):
    type = "date"
    baserow_field_type = "date"
    user_overridable_formatting_option_fields = [
        "date_format",
        "date_include_time",
        "date_time_format",
        "date_show_tzinfo",
        "date_force_timezone",
    ]
    nullable_option_fields = ["date_force_timezone"]
    can_represent_date = True
    can_order_by_in_array = True
    can_group_by = True
    can_have_db_index = True

    def __init__(
        self,
        date_format: str,
        date_include_time: bool,
        date_time_format: str,
        date_show_tzinfo: bool = False,
        date_force_timezone: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.date_format = date_format
        self.date_include_time = date_include_time
        self.date_time_format = date_time_format
        self.date_show_tzinfo = date_show_tzinfo
        self.date_force_timezone = date_force_timezone

    @property
    def comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [
            type(self),
            BaserowFormulaTextType,
        ]

    @property
    def limit_comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [type(self)]

    @property
    def addable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [BaserowFormulaDateIntervalType, BaserowFormulaDurationType]

    @property
    def subtractable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [type(self), BaserowFormulaDateIntervalType, BaserowFormulaDurationType]

    def get_in_array_empty_value(self, field: "Field") -> Any:
        return None

    def add(
        self,
        add_func_call: "BaserowFunctionCall[UnTyped]",
        arg1: "BaserowExpression[BaserowFormulaValidType]",
        arg2: "BaserowExpression[BaserowFormulaValidType]",
    ):
        return add_func_call.with_valid_type(
            _calculate_addition_interval_type(arg1, arg2)
        )

    def minus(
        self,
        minus_func_call: "BaserowFunctionCall[UnTyped]",
        arg1: "BaserowExpression[BaserowFormulaValidType]",
        arg2: "BaserowExpression[BaserowFormulaValidType]",
    ):
        arg1_type = arg1.expression_type
        arg2_type = arg2.expression_type
        if isinstance(arg2_type, BaserowFormulaDateType):
            # date - date = duration
            resulting_type = BaserowFormulaDurationType(
                nullable=arg1_type.nullable or arg2_type.nullable
            )
        else:
            # date - duration = date
            resulting_type = arg1_type
        return minus_func_call.with_valid_type(resulting_type)

    def should_recreate_when_old_type_was(self, old_type: "BaserowFormulaType") -> bool:
        if isinstance(old_type, BaserowFormulaDateType):
            return self.date_include_time != old_type.date_include_time
        else:
            return True

    def wrap_at_field_level(self, expr: "BaserowExpression[BaserowFormulaType]"):
        wrapped = formula_function_registry.get("bc_to_null")(expr)
        return super().wrap_at_field_level(wrapped)

    def unwrap_at_field_level(self, expr: "BaserowFunctionCall[BaserowFormulaType]"):
        unwrapped = super().unwrap_at_field_level(expr)
        return unwrapped.args[0].with_valid_type(unwrapped.expression_type)

    def cast_to_text(
        self,
        to_text_func_call: BaserowFunctionCall[UnTyped],
        arg: BaserowExpression[BaserowFormulaValidType],
    ) -> BaserowExpression[BaserowFormulaValidType]:
        when_empty = formula_function_registry.get("when_empty")
        datetime_format_tz = formula_function_registry.get("datetime_format_tz")
        date_format_string = literal(get_date_time_format(self, "sql"))
        convert_to_timezone = literal(self.date_force_timezone or "UTC")

        return when_empty(
            datetime_format_tz(arg, date_format_string, convert_to_timezone),
            literal(""),
        )

    def placeholder_empty_value(self):
        if self.date_include_time:
            field = models.DateTimeField()
        else:
            field = models.DateField()

        return Value(datetime.now(tz=timezone.utc), output_field=field)

    def get_search_expression_in_array(self, field, queryset):
        def transform_value_to_text_func(x):
            return Func(
                Func(
                    # FIXME: what if date_force_timezone is None(user timezone)?
                    Value(field.date_force_timezone or "UTC"),
                    Cast(x, output_field=models.DateTimeField()),
                    function="timezone",
                    output_field=models.DateTimeField(),
                ),
                Value(get_date_time_format(self, "sql")),
                function="to_char",
                output_field=models.TextField(),
            )

        return extract_jsonb_array_values_to_single_string(
            field,
            queryset,
            transform_value_to_text_func=transform_value_to_text_func,
        )

    def get_order_by_in_array_expr(self, field, field_name, order_direction):
        return JSONBSingleKeyArrayExpression(
            field_name, "value", "timestamp", output_field=models.DateTimeField()
        )

    def __str__(self) -> str:
        date_or_datetime = "datetime" if self.date_include_time else "date"
        optional_time_format = (
            f", {self.date_time_format}" if self.date_include_time else ""
        )
        return f"{date_or_datetime}({self.date_format}{optional_time_format})"


class BaserowFormulaSingleFileType(
    HasValueEmptyFilterSupport, BaserowJSONBObjectBaseType
):
    type = "single_file"
    can_group_by = False
    can_order_by = False
    can_order_by_in_array = False
    baserow_field_type = None
    item_is_in_nested_value_object_when_in_array = False
    can_represent_files = True

    def is_searchable(self, field):
        return True

    def placeholder_empty_value(self):
        return Value(None, output_field=JSONField())

    @property
    def comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [type(self)]

    @property
    def limit_comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return []

    @property
    def db_column_fields(self) -> Set[str]:
        return {}

    def get_all_empty_query(
        self,
        field_name: str,
        model_field: Field,
        field,
        in_array: bool = True,
    ) -> OptionallyAnnotatedQ:
        empty_value = self.get_in_array_empty_value(field)
        any_not_empty = get_jsonb_has_any_in_value_filter_expr(
            model_field,
            empty_value,
            query_path="$[*].name",
            comparison_operator="!=",
            join_operator="&&",
        )
        return AnnotatedQ(
            annotation=any_not_empty.annotation,
            q=~any_not_empty.q | Q(**{f"{field_name}": Value([], JSONField())}),
        )

    def get_in_array_empty_query(
        self, field_name, model_field, field
    ) -> OptionallyAnnotatedQ:
        # Use get_jsonb_has_any_in_value_filter_expr with size() to check if the array
        # is empty.
        return get_jsonb_has_any_in_value_filter_expr(
            model_field, [0], query_path="$[*].size()"
        )

    def get_model_field(self, instance, **kwargs) -> models.Field:
        return JSONField(default=dict, **kwargs)

    def get_baserow_field_instance_and_type(self):
        return self, self

    def get_response_serializer_field(self, instance, **kwargs):
        from baserow.contrib.database.api.fields.serializers import (
            FileFieldResponseSerializer,
        )

        return FileFieldResponseSerializer(**{"required": False, **kwargs})

    def get_serializer_field(self, instance, **kwargs):
        required = kwargs.get("required", False)
        from baserow.contrib.database.api.fields.serializers import (
            FileFieldRequestSerializer,
        )

        return FileFieldRequestSerializer(
            **{
                "required": required,
                "allow_null": not required,
                **kwargs,
            }
        )

    def get_export_value(self, value, field_object, rich_value=False) -> Any:
        file = value
        if "url" in file:
            url = file["url"]
        elif "name" in file:
            from baserow.core.user_files.handler import UserFileHandler

            storage = get_default_storage()

            path = UserFileHandler().user_file_path(file["name"])
            url = storage.url(path)
        else:
            url = None

        export_file = {
            "visible_name": file["visible_name"],
            "name": file["name"],
            "url": url,
        }

        if rich_value:
            return {
                "visible_name": export_file["visible_name"],
                "url": export_file["url"],
            }
        else:
            return f'{export_file["visible_name"]}({export_file["url"]})'

    def contains_query(self, field_name, value, model_field, field):
        value = value.strip()
        # If an empty value has been provided we do not want to filter at all.
        if value == "":
            return Q()
        return Q(**{f"{field_name}__visible_name__icontains": value})

    def get_alter_column_prepare_old_value(self, connection, from_field, to_field):
        sql = f"""
            p_in = p_in->'visible_name';
        """
        return sql, {}

    def get_human_readable_value(self, value, field_object) -> str:
        if value is None:
            return ""
        return self.get_export_value(value, field_object, rich_value=False) or ""

    def cast_to_text(
        self,
        to_text_func_call: "BaserowFunctionCall[UnTyped]",
        arg: "BaserowExpression[BaserowFormulaValidType]",
    ) -> "BaserowExpression[BaserowFormulaType]":
        single_select_value = formula_function_registry.get("get_single_select_value")(
            arg
        )
        return formula_function_registry.get("when_empty")(
            single_select_value, literal("")
        )

    def get_search_expression(self, field, queryset):
        return Cast(
            F(field.db_column + "__visible_name"), output_field=models.TextField()
        )

    def get_search_expression_in_array(self, field, queryset):
        return extract_jsonb_array_values_to_single_string(
            field,
            queryset,
            path_to_value_in_jsonb_list=[
                Value("visible_name", output_field=models.TextField()),
            ],
        )


class BaserowFormulaArrayType(
    BaserowFormulaArrayFilterSupportMixin,
    BaserowFormulaValidType,
):
    type = "array"
    user_overridable_formatting_option_fields = [
        "array_formula_type",
    ]
    can_group_by = False
    serializer_extra_args = ["limit_linked_items"]

    def __init__(self, sub_type: BaserowFormulaValidType, **kwargs):
        super().__init__(**kwargs)
        self.array_formula_type = sub_type.type
        self.sub_type = sub_type

    def get_search_expression(self, field, queryset):
        return self.sub_type.get_search_expression_in_array(field, queryset)

    def is_searchable(self, field):
        return True

    @classmethod
    def construct_type_from_formula_field(cls, formula_field):
        sub_type_cls = _lookup_formula_type_from_string(
            formula_field.array_formula_type
        )
        sub_type = sub_type_cls.construct_type_from_formula_field(formula_field)
        return cls(sub_type)

    def persist_onto_formula_field(self, formula_field):
        self.sub_type.persist_onto_formula_field(formula_field)
        formula_field.array_formula_type = self.sub_type.type
        formula_field.formula_type = self.type

    def new_type_with_user_and_calculated_options_merged(self, formula_field):
        new_sub_type = self.sub_type.new_type_with_user_and_calculated_options_merged(
            formula_field
        )
        return self.__class__(new_sub_type)

    def collapse_many(self, expr: "BaserowExpression[BaserowFormulaType]"):
        return expr.expression_type.sub_type.collapse_array_of_many(expr)

    def placeholder_empty_value(self):
        """
        The use of `array_agg_unnesting` in `self.collapse_many` above means that we can
        never have null values inserted into array fields but instead they should be
        empty lists.

        This is because during template imports we can run update statements using
        `array_agg_unnesting` over array fields which have just been filled with empty
        data and not had their actual values calculated yet. If they instead defaulted
        to Value(None) (null) these update statements would fail as the use of
        `jsonb_array_elements` by `array_agg_unnesting` crashes if you give in null
        instead of [] with
        `django.db.utils.DataError: cannot extract elements from a scalar`
        """

        return Value([], output_field=JSONField())

    def wrap_at_field_level(self, expr: "BaserowExpression[BaserowFormulaType]"):
        return formula_function_registry.get("error_to_null")(expr)

    def unwrap_at_field_level(self, expr: "BaserowFunctionCall[BaserowFormulaType]"):
        arg = expr.args[0]
        # By unwrapping a field's array_agg we can then use our own aggregate
        # functions or apply our own transformations on the underlying many
        # expression.
        single_unnest = formula_function_registry.get("array_agg")
        double_unnest = formula_function_registry.get("array_agg_unnesting")
        multiple_select_agg = formula_function_registry.get(
            "multiple_select_options_agg"
        )
        many_to_many_agg = formula_function_registry.get("many_to_many_agg")

        sub_type = expr.expression_type.sub_type
        if isinstance(arg, BaserowFunctionCall):
            if arg.function_def.type in (
                single_unnest.type,
                multiple_select_agg.type,
                many_to_many_agg.type,
            ):
                arg = arg.args[0]
            elif arg.function_def.type == double_unnest.type:
                arg = arg.args[0]
                sub_type = BaserowFormulaArrayType(sub_type)
        elif isinstance(arg, BaserowFieldReference):
            sub_type = BaserowFormulaArrayType(sub_type)

        return arg.with_valid_type(sub_type)

    @property
    def baserow_field_type(self) -> str:
        return "unknown"

    @property
    def comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return []

    @property
    def limit_comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return []

    def get_baserow_field_instance_and_type(self):
        # Until Baserow has a array field type implement the required methods below
        return self, self

    @property
    def db_column_fields(self) -> Set[str]:
        return {}

    def get_model_field(self, instance, **kwargs) -> models.Field:
        return JSONField(default=list, **kwargs)

    def get_response_serializer_field(self, instance, **kwargs) -> Optional[Field]:
        return self.get_serializer_field(instance, **kwargs)

    def get_serializer_field(self, instance, **kwargs) -> Optional[Field]:
        required = kwargs.get("required", False)

        from baserow.contrib.database.api.fields.serializers import (
            ArrayValueSerializer,
            LimitListSerializer,
        )

        (
            instance,
            field_type,
        ) = self.sub_type.get_baserow_field_instance_and_type()
        if self.sub_type.item_is_in_nested_value_object_when_in_array:
            serializer = ArrayValueSerializer(
                field_type.get_response_serializer_field(instance)
            )
        else:
            serializer = field_type.get_response_serializer_field(instance)
        return LimitListSerializer(
            **{
                "required": required,
                "allow_null": not required,
                "child": serializer,
                "limit": kwargs.pop("limit_linked_items", None),
                **kwargs,
            }
        )

    def get_export_value(self, value, field_object, rich_value=False) -> Any:
        if value is None:
            return [] if rich_value else ""

        field_instance, field_type = self.sub_type.get_baserow_field_instance_and_type()
        field_obj = {
            "field": field_instance,
            "type": field_type,
            "name": field_object["name"],
            "formula_field": field_object["formula_field"],
        }

        result = self._map_safely_across_lookup_json_value_list(
            lambda safe_value: field_type.get_export_value(
                safe_value, field_obj, rich_value=rich_value
            ),
            value,
        )

        if rich_value:
            return result
        else:
            return list_to_comma_separated_string(result)

    def contains_query(self, field_name, value, model_field, field):
        return Q()

    def get_alter_column_prepare_old_value(self, connection, from_field, to_field):
        return "p_in = '';"

    def get_human_readable_value(self, value: Any, field_object) -> str:
        if value is None:
            return ""

        field_instance, field_type = self.sub_type.get_baserow_field_instance_and_type()
        field_obj = {
            "field": field_instance,
            "type": field_type,
            "name": field_object["name"],
            "formula_field": field_object["formula_field"],
        }

        human_readable_values = self._map_safely_across_lookup_json_value_list(
            lambda safe_value: field_type.get_human_readable_value(
                safe_value, field_obj
            ),
            value,
        )

        return ", ".join(human_readable_values)

    def _map_safely_across_lookup_json_value_list(
        self, map_func, lookup_json_value_list
    ):
        human_readable_values = []
        for v in lookup_json_value_list:
            if self.sub_type.item_is_in_nested_value_object_when_in_array:
                list_item = v["value"]
            else:
                list_item = v
            if list_item is not None and self.sub_type.type == "date":
                # Arrays are stored as JSON which means the dates are converted to
                # strings, we need to reparse them back first before giving it to
                # the date field type.
                list_item = parser.isoparse(list_item)
            elif list_item is not None and self.sub_type.type == "duration":
                # Arrays are stored as JSON which means the durations are converted to
                # a string, we need to parse them back first before
                # giving the duration field type.
                total_seconds = postgres_interval_to_seconds(list_item)
                list_item = timedelta(seconds=total_seconds)
            export_value = map_func(list_item)
            if export_value is None:
                export_value = ""
            human_readable_values.append(export_value)
        return human_readable_values

    @property
    def can_order_by(self) -> bool:
        return self.sub_type.can_order_by_in_array

    def get_order(
        self, field, field_name, order_direction, table_model=None
    ) -> OptionallyAnnotatedOrderBy:
        expr = self.sub_type.get_order_by_in_array_expr(
            field, field_name, order_direction
        )
        annotation_name = f"{field_name}_agg_sort_array"
        annotation = {annotation_name: expr}
        field_expr = F(annotation_name)

        if order_direction == "ASC":
            field_order_by = field_expr.asc(nulls_first=True)
        else:
            field_order_by = field_expr.desc(nulls_last=True)

        return OptionallyAnnotatedOrderBy(
            annotation=annotation, order=field_order_by, can_be_indexed=False
        )

    def get_value_for_filter(self, row, field) -> any:
        return None

    def check_if_compatible_with(self, compatible_formula_types: List[str]):
        self_as_str = self.formula_array_type_as_str(self.sub_type.type)
        return self_as_str in compatible_formula_types

    def __str__(self) -> str:
        return self.formula_array_type_as_str(self.sub_type)

    @classmethod
    def formula_array_type_as_str(cls, sub_type):
        return f"array({sub_type})"

    def can_represent_files(self, field):
        return self.sub_type.can_represent_files(field)

    def can_represent_select_options(self, field) -> bool:
        return self.sub_type.can_represent_select_options(field)

    def can_represent_collaborators(self, field):
        return self.sub_type.can_represent_collaborators(field)

    @classmethod
    def get_serializer_field_overrides(cls):
        from baserow.contrib.database.api.fields.serializers import (
            AvailableCollaboratorsSerializer,
            SelectOptionSerializer,
        )
        from baserow.contrib.database.api.formula.serializers import (
            BaserowFormulaSelectOptionsSerializer,
        )

        return {
            "select_options": BaserowFormulaSelectOptionsSerializer(
                child=SelectOptionSerializer(),
                required=False,
                allow_null=True,
                read_only=True,
            ),
            "available_collaborators": AvailableCollaboratorsSerializer(
                required=False, allow_null=True
            ),
        }

    def parse_filter_value(self, field, model_field, value):
        return self.sub_type.parse_filter_value(field, model_field, value)


class BaserowFormulaSingleSelectType(
    SingleSelectFormulaTypeFilterSupport,
    BaserowJSONBObjectBaseType,
):
    type = "single_select"
    baserow_field_type = "single_select"
    can_order_by = True
    can_order_by_in_array = True
    can_group_by = False

    @property
    def comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [
            type(self),
            BaserowFormulaTextType,
        ]

    @property
    def can_represent_select_options(self) -> bool:
        return True

    @property
    def limit_comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return []

    def get_baserow_field_instance_and_type(self):
        return self, self

    @property
    def db_column_fields(self) -> Set[str]:
        return {}

    def get_model_field(self, instance, **kwargs) -> models.Field:
        return JSONField(default=dict, **kwargs)

    def get_response_serializer_field(self, instance, **kwargs) -> Optional[Field]:
        instance, field_type = super().get_baserow_field_instance_and_type()
        return field_type.get_response_serializer_field(instance, **kwargs)

    def get_serializer_field(self, *args, **kwargs) -> Optional[Field]:
        instance, field_type = super().get_baserow_field_instance_and_type()
        return field_type.get_response_serializer_field(instance, **kwargs)

    def get_export_value(self, value, field_object, rich_value=False) -> Any:
        if value is None:
            return value if rich_value else ""
        return value["value"]

    def contains_query(self, field_name, value, model_field, field):
        value = value.strip()
        # If an empty value has been provided we do not want to filter at all.
        if value == "":
            return Q()
        return Q(**{f"{field_name}__value__icontains": value})

    def contains_word_query(self, field_name, value, model_field, field):
        value = value.strip()
        # If an empty value has been provided we do not want to filter at all.
        if value == "":
            return Q()
        value = re.escape(value)
        return Q(**{f"{field_name}__value__iregex": rf"\m{value}\M"})

    def get_alter_column_prepare_old_value(self, connection, from_field, to_field):
        sql = f"""
            p_in = p_in->'value';
        """
        return sql, {}

    def get_human_readable_value(self, value, field_object) -> str:
        if value is None:
            return ""
        return self.get_export_value(value, field_object, rich_value=False) or ""

    def cast_to_text(
        self,
        to_text_func_call: "BaserowFunctionCall[UnTyped]",
        arg: "BaserowExpression[BaserowFormulaValidType]",
    ) -> "BaserowExpression[BaserowFormulaType]":
        single_select_value = formula_function_registry.get("get_single_select_value")(
            arg
        )
        return formula_function_registry.get("when_empty")(
            single_select_value, literal("")
        )

    def get_search_expression(self, field, queryset):
        return Cast(F(field.db_column + "__value"), output_field=models.TextField())

    def get_search_expression_in_array(self, field, queryset):
        return extract_jsonb_array_values_to_single_string(
            field,
            queryset,
            path_to_value_in_jsonb_list=[
                Value("value", output_field=models.TextField()),
                Value("value", output_field=models.TextField()),
            ],
        )

    def is_searchable(self, field):
        return True

    def get_order(
        self, field, field_name, order_direction, table_model=None
    ) -> OptionallyAnnotatedOrderBy:
        field_expr = collate_expression(Cast(F(f"{field_name}__value"), TextField()))

        if order_direction == "ASC":
            field_order_by = field_expr.asc(nulls_first=True)
        else:
            field_order_by = field_expr.desc(nulls_last=True)

        return OptionallyAnnotatedOrderBy(order=field_order_by, can_be_indexed=True)

    def get_value_for_filter(self, row, field) -> any:
        return getattr(row, field.db_column)["value"]

    def get_order_by_in_array_expr(self, field, field_name, order_direction):
        return JSONBSingleInnerKeyArrayExpression(
            field_name,
            "value",
            "jsonb",
            "value",
            "text",
            output_field=ArrayField(
                base_field=models.DecimalField(max_digits=50, decimal_places=0)
            ),
        )

    @classmethod
    def get_serializer_field_names(cls) -> List[str]:
        return super().all_fields() + ["select_options"]

    @classmethod
    def get_serializer_field_overrides(cls):
        from baserow.contrib.database.api.fields.serializers import (
            SelectOptionSerializer,
        )
        from baserow.contrib.database.api.formula.serializers import (
            BaserowFormulaSelectOptionsSerializer,
        )

        return {
            "select_options": BaserowFormulaSelectOptionsSerializer(
                child=SelectOptionSerializer(),
                required=False,
                allow_null=True,
                read_only=True,
            )
        }


class BaserowFormulaMultipleSelectType(
    MultipleSelectFormulaTypeFilterSupport, BaserowJSONBObjectBaseType
):
    type = "multiple_select"
    baserow_field_type = "multiple_select"
    can_order_by = False
    can_order_by_in_array = False
    can_group_by = False

    @property
    def comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [type(self)]

    @property
    def limit_comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return []

    def get_baserow_field_instance_and_type(self):
        return self, self

    def get_alter_column_prepare_old_value(self, connection, from_field, to_field):
        return "p_in = '';"

    @property
    def can_represent_select_options(self) -> bool:
        return True

    @property
    def db_column_fields(self) -> Set[str]:
        return {}

    def get_model_field(self, instance, **kwargs) -> models.Field:
        return JSONField(default=list, **kwargs)

    def get_response_serializer_field(self, instance, **kwargs) -> Optional[Field]:
        instance, field_type = super().get_baserow_field_instance_and_type()
        return field_type.get_response_serializer_field(instance, **kwargs)

    def get_serializer_field(self, *args, **kwargs) -> Optional[Field]:
        instance, field_type = super().get_baserow_field_instance_and_type()
        return field_type.get_response_serializer_field(instance, **kwargs)

    def get_export_value(self, value, field_object, rich_value=False):
        if value is None:
            return [] if rich_value else ""

        result = [item["value"] for item in value]

        if rich_value:
            return result
        else:
            return list_to_comma_separated_string(result)

    def get_human_readable_value(self, value, field_object):
        export_value = self.get_export_value(value, field_object, rich_value=True)

        return ", ".join(export_value)

    def is_searchable(self, field):
        return True

    def get_search_expression(self, field, queryset):
        return extract_jsonb_array_values_to_single_string(
            field, queryset, [Value("value")]
        )

    def get_search_expression_in_array(self, field, queryset):
        inner_expr = json_extract_path(
            Func(
                F(field.db_column),
                function="jsonb_array_elements",
                output_field=JSONField(),
            ),
            [Value("value")],
            False,
        )

        return Func(
            extract_jsonb_list_values_to_array(queryset, inner_expr, [Value("value")]),
            Value(" "),
            function="array_to_string",
            output_field=TextField(),
        )

    def cast_to_text(
        self,
        to_text_func_call: "BaserowFunctionCall[UnTyped]",
        arg: "BaserowExpression[BaserowFormulaValidType]",
    ) -> "BaserowExpression[BaserowFormulaType]":
        join_multiple_select_values = formula_function_registry.get(
            "string_agg_many_to_many_values"
        )
        when_empty = formula_function_registry.get("when_empty")
        return when_empty(join_multiple_select_values(arg), literal(""))

    def is_blank(
        self,
        func_call: BaserowFunctionCall[UnTyped],
        arg: BaserowExpression[BaserowFormulaValidType],
    ) -> BaserowExpression[BaserowFormulaBooleanType]:
        equal_expr = formula_function_registry.get("equal")
        count_expr = formula_function_registry.get("many_to_many_count")
        return equal_expr(count_expr(arg), literal(0))

    def collapse_many(self, expr: BaserowExpression[BaserowFormulaType]):
        return formula_function_registry.get("many_to_many_agg")(expr)

    def count(
        self,
        func_call: BaserowFunctionCall[UnTyped],
        arg: BaserowExpression[BaserowFormulaValidType],
    ) -> BaserowExpression[BaserowFormulaType]:
        return formula_function_registry.get("many_to_many_count")(arg)

    def contains_query(self, field_name, value, model_field, field):
        return get_jsonb_contains_filter_expr(model_field, value)

    def contains_word_query(self, field_name, value, model_field, field):
        return get_jsonb_contains_word_filter_expr(model_field, value)


class BaserowFormulaMultipleCollaboratorsType(
    HasValueContainsWordFilterSupport,
    HasValueContainsFilterSupport,
    HasValueEmptyFilterSupport,
    HasValueEqualFilterSupport,
    BaserowJSONBObjectBaseType,
):
    type = "multiple_collaborators"
    baserow_field_type = "multiple_collaborators"
    can_order_by = False
    can_order_by_in_array = False
    can_group_by = False

    def get_in_array_contains_word_query(
        self, field_name: str, value: str, model_field: DjangoField, field: "Field"
    ) -> OptionallyAnnotatedQ:
        return get_jsonb_contains_word_filter_expr(
            model_field, value, query_path="$[*].value.first_name"
        )

    def get_in_array_contains_query(
        self, field_name: str, value: str, model_field: DjangoField, field: "Field"
    ) -> OptionallyAnnotatedQ:
        return get_jsonb_contains_filter_expr(
            model_field, value, query_path="$[*].value.first_name"
        )

    def get_in_array_is_query(
        self, field_name: str, value: str, model_field: DjangoField, field: "Field"
    ) -> OptionallyAnnotatedQ:
        try:
            value = [int(value)]

        except (TypeError, ValueError):
            return Q()

        return get_jsonb_has_any_in_value_filter_expr(
            model_field, value, query_path="$[*].value.id"
        )

    def get_in_array_empty_query(
        self, field_name: str, model_field: DjangoField, field: "Field"
    ) -> OptionallyAnnotatedQ:
        return get_jsonb_has_any_in_value_filter_expr(
            model_field, [0], query_path="$[*].value.size()"
        )

    def get_all_empty_query(
        self, field_name: str, model_field: Field, field, in_array: bool = True
    ) -> OptionallyAnnotatedQ:
        if in_array:
            any_not_empty = get_jsonb_has_any_in_value_filter_expr(
                model_field,
                [0],
                query_path="$[*].value.size()",
                comparison_operator=">",
                join_operator="&&",
            )
        else:
            empty_value = self.get_in_array_empty_value(field)
            any_not_empty = get_jsonb_has_any_in_value_filter_expr(
                model_field,
                empty_value,
                query_path=f"$[*].first_name",
                comparison_operator="!=",
                join_operator="&&",
            )
        return AnnotatedQ(
            annotation=any_not_empty.annotation,
            q=~any_not_empty.q | Q(**{f"{field_name}": Value([], JSONField())}),
        )

    @property
    def comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return [type(self)]

    @property
    def limit_comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return []

    def get_baserow_field_instance_and_type(self):
        return self, self

    def get_alter_column_prepare_old_value(self, connection, from_field, to_field):
        return "p_in = '';"

    @property
    def can_represent_collaborators(self) -> bool:
        return True

    @property
    def db_column_fields(self) -> Set[str]:
        return {}

    def get_model_field(self, instance, **kwargs) -> models.Field:
        return JSONField(default=list, **kwargs)

    def get_response_serializer_field(self, instance, **kwargs) -> Optional[Field]:
        instance, field_type = super().get_baserow_field_instance_and_type()
        return field_type.get_response_serializer_field(instance, **kwargs)

    def get_serializer_field(self, *args, **kwargs) -> Optional[Field]:
        instance, field_type = super().get_baserow_field_instance_and_type()
        return field_type.get_response_serializer_field(instance, **kwargs)

    def get_export_value(self, value, field_object, rich_value=False):
        _, field_type = super().get_baserow_field_instance_and_type()

        cache_key = f"_baserow_cache_{field_object['name']}_relations"
        field = field_object["formula_field"]
        if not hasattr(field, cache_key):
            setattr(
                field,
                cache_key,
                {usr.id: usr for usr in field.table.database.workspace.users.all()},
            )

        # Replace the JSON object with the actual user object, so we have
        # access to the user's email.
        users = getattr(field, cache_key)
        value = [users[item["id"]] for item in value]

        return field_type.get_export_value(value, field_object, rich_value=rich_value)

    def get_human_readable_value(self, value, field_object):
        export_value = self.get_export_value(value, field_object, rich_value=True)

        return ", ".join(export_value)

    def is_searchable(self, field):
        return True

    def get_search_expression(self, field, queryset):
        return extract_jsonb_array_values_to_single_string(
            field, queryset, [Value("first_name")]
        )

    def get_search_expression_in_array(self, field, queryset):
        inner_expr = json_extract_path(
            Func(
                F(field.db_column),
                function="jsonb_array_elements",
                output_field=JSONField(),
            ),
            [Value("value")],
            False,
        )

        return Func(
            extract_jsonb_list_values_to_array(
                queryset, inner_expr, [Value("first_name")]
            ),
            Value(" "),
            function="array_to_string",
            output_field=TextField(),
        )

    def cast_to_text(
        self,
        to_text_func_call: "BaserowFunctionCall[UnTyped]",
        arg: "BaserowExpression[BaserowFormulaValidType]",
    ) -> "BaserowExpression[BaserowFormulaType]":
        join_multiple_select_values = formula_function_registry.get(
            "string_agg_many_to_many_values"
        )
        when_empty = formula_function_registry.get("when_empty")
        return when_empty(join_multiple_select_values(arg), literal(""))

    def is_blank(
        self,
        func_call: BaserowFunctionCall[UnTyped],
        arg: BaserowExpression[BaserowFormulaValidType],
    ) -> BaserowExpression[BaserowFormulaBooleanType]:
        equal_expr = formula_function_registry.get("equal")
        count_expr = formula_function_registry.get("many_to_many_count")
        return equal_expr(count_expr(arg), literal(0))

    def collapse_many(self, expr: BaserowExpression[BaserowFormulaType]):
        return formula_function_registry.get("many_to_many_agg")(expr)

    def count(
        self,
        func_call: BaserowFunctionCall[UnTyped],
        arg: BaserowExpression[BaserowFormulaValidType],
    ) -> BaserowExpression[BaserowFormulaType]:
        return formula_function_registry.get("many_to_many_count")(arg)

    @property
    def custom_string_agg_value_key(self):
        """
        The key in the JSON object that contains the value that should be used for
        string aggregation.
        """

        return "first_name"

    @classmethod
    def get_serializer_field_overrides(cls):
        from baserow.contrib.database.api.fields.serializers import (
            AvailableCollaboratorsSerializer,
        )

        return {
            "available_collaborators": AvailableCollaboratorsSerializer(
                allow_null=True, required=False
            )
        }

    @classmethod
    def get_serializer_field_names(cls) -> List[str]:
        return super().all_fields() + ["available_collaborators"]


BASEROW_FORMULA_TYPES = [
    BaserowFormulaInvalidType,
    BaserowFormulaTextType,
    BaserowFormulaCharType,
    BaserowFormulaButtonType,
    BaserowFormulaLinkType,
    BaserowFormulaDateIntervalType,  # Deprecated in favor of BaserowFormulaDurationType
    BaserowFormulaDurationType,
    BaserowFormulaDateType,
    BaserowFormulaBooleanType,
    BaserowFormulaNumberType,
    BaserowFormulaArrayType,
    BaserowFormulaSingleSelectType,
    BaserowFormulaMultipleSelectType,
    BaserowFormulaSingleFileType,
    BaserowFormulaURLType,
    BaserowFormulaMultipleCollaboratorsType,
]

BASEROW_FORMULA_TYPE_ALLOWED_FIELDS = list(
    set(
        allowed_field for f in BASEROW_FORMULA_TYPES for allowed_field in f.all_fields()
    )
)

BASEROW_FORMULA_TYPE_CHOICES = [(f.type, f.type) for f in BASEROW_FORMULA_TYPES]
BASEROW_FORMULA_ARRAY_TYPE_CHOICES = [
    (f.type, f.type)
    for f in BASEROW_FORMULA_TYPES
    if f.type != BaserowFormulaArrayType.type
]

BASEROW_FORMULA_TYPE_SERIALIZER_FIELD_NAMES = list(
    set(
        allowed_field
        for f in BASEROW_FORMULA_TYPES
        for allowed_field in f.get_serializer_field_names()
    )
)
BASEROW_FORMULA_TYPE_REQUEST_SERIALIZER_FIELD_NAMES = list(
    set(
        allowed_field
        for f in BASEROW_FORMULA_TYPES
        for allowed_field in f.get_request_serializer_field_names()
    )
)


def get_baserow_formula_type_serializer_field_overrides():
    return {
        key: value
        for f in BASEROW_FORMULA_TYPES
        for key, value in f.get_serializer_field_overrides().items()
    }


def calculate_number_type(
    arg_types: List[BaserowFormulaNumberType], min_decimal_places=0
):
    max_number_decimal_places = min_decimal_places
    number_prefix = ""
    number_suffix = ""
    number_separator = ""
    number_settings_set = False
    for a in arg_types:
        max_number_decimal_places = max(
            max_number_decimal_places, a.number_decimal_places
        )
        if not number_settings_set and (
            a.number_prefix or a.number_suffix or a.number_separator
        ):
            # If we have not set the number settings yet, we will use the first
            number_prefix = a.number_prefix
            number_suffix = a.number_suffix
            number_separator = a.number_separator
            number_settings_set = True

    return BaserowFormulaNumberType(
        number_decimal_places=max_number_decimal_places,
        number_prefix=number_prefix,
        number_suffix=number_suffix,
        number_separator=number_separator,
    )


def _lookup_formula_type_from_string(formula_type_string):
    for possible_type in BASEROW_FORMULA_TYPES:
        if formula_type_string == possible_type.type:
            return possible_type
    raise UnknownFormulaType(formula_type_string)


def literal(
    arg: Union[str, int, bool, Decimal]
) -> BaserowExpression[BaserowFormulaValidType]:
    """
    A helper function for building BaserowExpressions with literals
    :param arg: The literal
    :return: The literal wrapped in the corresponding valid typed BaserowExpression
        literal.
    """

    if isinstance(arg, str):
        return BaserowStringLiteral(arg, BaserowFormulaTextType())
    elif isinstance(arg, bool):
        return BaserowBooleanLiteral(arg, BaserowFormulaBooleanType())
    elif isinstance(arg, int):
        return BaserowIntegerLiteral(
            arg, BaserowFormulaNumberType(number_decimal_places=0)
        )
    elif isinstance(arg, Decimal):
        decimal_literal_expr = BaserowDecimalLiteral(arg, None)
        return decimal_literal_expr.with_valid_type(
            BaserowFormulaNumberType(decimal_literal_expr.num_decimal_places())
        )
    else:
        raise TypeError(f"Unknown literal type {type(arg)}")


class JSONBSingleKeyArrayExpression(Expression):
    template = """
        (
            SELECT ARRAY_AGG(items.{key_name})
            FROM jsonb_to_recordset({field_name}) as items(
            {key_name} {data_type})
        )
        """  # nosec B608
    # fmt: on

    def __init__(self, field_name: str, key_name: str, data_type: str, **kwargs):
        super().__init__(**kwargs)
        self.field_name = field_name
        self.key_name = key_name
        self.data_type = data_type

    def as_sql(self, compiler, connection, template=None):
        template = template or self.template
        data = {
            "field_name": f'"{self.field_name}"',
            "key_name": f'"{self.key_name}"',
            "data_type": self.data_type,
        }

        return template.format(**data), []


class JSONBSingleInnerKeyArrayExpression(Expression):
    template = """
        (
            SELECT ARRAY_AGG(items.{key_name}->>{inner_key_name}::{inner_data_type})
            FROM jsonb_to_recordset({field_name}) as items(
            {key_name} {data_type})
        )
        """  # nosec B608
    # fmt: on

    def __init__(
        self,
        field_name: str,
        key_name: str,
        data_type: str,
        inner_key_name: str,
        inner_data_type: str,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.field_name = field_name
        self.key_name = key_name
        self.data_type = data_type
        self.inner_key_name = inner_key_name
        self.inner_data_type = inner_data_type

    def as_sql(self, compiler, connection, template=None):
        template = template or self.template
        data = {
            "field_name": f'"{self.field_name}"',
            "key_name": f'"{self.key_name}"',
            "data_type": self.data_type,
            "inner_key_name": f"'{self.inner_key_name}'",
            "inner_data_type": self.inner_data_type,
        }

        return template.format(**data), []
