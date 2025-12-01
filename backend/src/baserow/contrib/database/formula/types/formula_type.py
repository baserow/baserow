import abc
from typing import TYPE_CHECKING, List, Type, TypeVar

from django.db.models import Expression, F, Model, Value
from django.utils.functional import classproperty

from baserow.contrib.database.fields.expressions import (
    extract_jsonb_array_values_to_single_string,
)
from baserow.contrib.database.fields.field_sortings import OptionallyAnnotatedOrderBy
from baserow.contrib.database.formula.ast import tree
from baserow.contrib.database.formula.registries import formula_function_registry
from baserow.contrib.database.formula.types.exceptions import InvalidFormulaType

T = TypeVar("T", bound="BaserowFormulaType")

if TYPE_CHECKING:
    from baserow.contrib.database.fields.models import FormulaField
    from baserow.contrib.database.fields.registries import FieldType
    from baserow.contrib.database.formula.types.formula_types import (
        BaserowFormulaBooleanType,
    )


EVERY_TYPE_INTERNAL_FIELDS = ["nullable"]


class BaserowFormulaTypeHasEmptyBaserowExpression(abc.ABC):
    @abc.abstractmethod
    def placeholder_empty_baserow_expression(self) -> Expression:
        """
        :return: A Django expression that can be used to represent an empty value for
        this type. This is used when a formula field is nullable and the formula
        returns an empty value.
        """

        pass

    def is_blank(
        self,
        func_call: "tree.BaserowFunctionCall[UnTyped]",
        arg: "tree.BaserowExpression[BaserowFormulaValidType]",
    ) -> "tree.BaserowExpression[BaserowFormulaBooleanType]":
        """
        Returns an expression which evaluates to true if the given expression is
        blank. Different formula types may have different definitions of what is
        blank (e.g. isblank(0) returns True for numbers, False for text ).
        """

        equal_expr = formula_function_registry.get("equal")
        return equal_expr(
            self.try_coerce_to_not_null(arg),
            self.placeholder_empty_baserow_expression(),
        )

    def try_coerce_to_not_null(
        self, expr: "tree.BaserowExpression[BaserowFormulaValidType]"
    ):
        placeholder_empty_baserow_expr = self.placeholder_empty_baserow_expression()
        return formula_function_registry.get("when_empty")(
            expr, placeholder_empty_baserow_expr
        )


class BaserowFormulaType(abc.ABC):
    @classmethod
    @property
    @abc.abstractmethod
    def type(cls) -> str:
        """
        Should be a unique lowercase string used to identify this type.
        """

        pass

    @property
    @abc.abstractmethod
    def baserow_field_type(self) -> str:
        """
        The Baserow field type that corresponds to this formula type and should be
        used to do various Baserow operations for a formula field of this type.
        """

        pass

    @classproperty
    def user_overridable_formatting_option_fields(cls) -> List[str]:
        """
        :return: The list of FormulaField model field names which control
        formatting for a formula field of this type and should be allowed to be
        controlled and set by a user.
        """

        return []

    @classproperty
    def nullable_option_fields(cls) -> List[str]:
        """
        :return: The list of FormulaField model field names which are nullable and
            the user should be able to override them to being null.
        """

        return []

    @classproperty
    def internal_fields(cls) -> List[str]:
        """
        :return: The list of FormulaField model field names which store internal
        information required for a formula of this type.
        """

        return []

    @classmethod
    def get_internal_fields(cls) -> List[str]:
        """
        :return: The list of FormulaField model field names which store internal
        information required for a formula of this type plus EVERY_TYPE_INTERNAL_FIELDS.
        """

        return EVERY_TYPE_INTERNAL_FIELDS + cls.internal_fields

    @classmethod
    def all_fields(cls) -> List[str]:
        """
        :returns All FormulaField model field names required for a formula field of
        this type.
        """

        return cls.user_overridable_formatting_option_fields + cls.get_internal_fields()

    @classmethod
    def get_request_serializer_field_names(cls) -> List[str]:
        return cls.all_fields()

    @classmethod
    def get_serializer_field_names(cls) -> List[str]:
        return cls.all_fields()

    @classmethod
    def get_serializer_field_overrides(cls) -> List[str]:
        return {}

    @property
    @abc.abstractmethod
    def comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        """
        A list of valid types that this type can be compared with in a formula.
        """

        pass

    @property
    def addable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        """
        A list of valid types that this type can be used with the addition operator
        in a formula.
        """

        return []

    @property
    def subtractable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        """
        A list of valid types that can be subtracted from this type in a formula.
        """

        return []

    @property
    def multipliable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return []

    @property
    def dividable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        return []

    @property
    @abc.abstractmethod
    def limit_comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        """
        A list of valid types that this type can be compared using limit operators like
        >, >=, < or <=.
        """

        pass

    @property
    @abc.abstractmethod
    def can_order_by(self) -> bool:
        """
        Return True if a formula field of this type can be ordered or False if not.
        """

        pass

    @property
    @abc.abstractmethod
    def can_group_by(self) -> bool:
        """
        Return True if a formula field of this type can be grouped or False if not.
        """

        pass

    def _get_order_field_expression(self, field_name: str) -> Expression | F:
        """
        Returns the field expression that should be used for ordering by the field
        with the given name. By default, this is just the field itself, but
        for some types, we might want to properly collate the expression or return
        a different one.

        :param field_name: The name of the field to order by.
        :return: The field expression that should be used for ordering by the field.
        """

        return F(field_name)

    def get_order(
        self, field, field_name, order_direction, table_model=None
    ) -> OptionallyAnnotatedOrderBy:
        """
        Returns OptionallyAnnotatedOrderBy with desired order and optional
        annotation that will be used as the order on the particular field.
        """

        field_expr = self._get_order_field_expression(field_name)

        if order_direction == "ASC":
            field_order_by = field_expr.asc(nulls_first=True)
        else:
            field_order_by = field_expr.desc(nulls_last=True)

        return OptionallyAnnotatedOrderBy(order=field_order_by, can_be_indexed=True)

    def get_value_for_filter(self, row, field) -> any:
        """
        Returns the value of a field in a row that can be used for SQL filtering.
        Usually this is just a string or int value stored in the row.

        Should be implemented when can_order_by_in_array is True.

        :param row: The row which contains the field value.
        :param field: The instance of the field to get the value for.
        :return: The value of the field in the row in a filterable format.
        """

        return getattr(row, field.db_column)

    @property
    def can_order_by_in_array(self) -> bool:
        """
        Return True if the type is sortable as an array formula subtype.

        If True, get_order_by_array_expr() method should be implemented for the subtype.
        """

        return False

    def get_order_by_in_array_expr(self, field, field_name, order_direction):
        """
        Can be used to aggregate values for ordering if can_order_by_in_array returns
        True.
        """

        raise NotImplementedError()

    @property
    def can_represent_date(self) -> bool:
        return False

    @property
    def can_represent_files(self) -> bool:
        return False

    @property
    def can_represent_select_options(self) -> bool:
        return False

    @property
    def can_represent_collaborators(self) -> bool:
        return False

    @property
    def item_is_in_nested_value_object_when_in_array(self) -> bool:
        return True

    @property
    def can_have_db_index(self) -> bool:
        return False

    @property
    @abc.abstractmethod
    def is_valid(self) -> bool:
        pass

    def is_invalid(self) -> bool:
        return not self.is_valid

    @abc.abstractmethod
    def raise_if_invalid(self):
        pass

    @classmethod
    def construct_type_from_formula_field(cls: Type[T], formula_field) -> T:
        """
        Creates a BaserowFormulaType instance based on what is set on the formula field.
        :param formula_field: The formula field to get type info from.
        :return: A new BaserowFormulaType.
        """

        kwargs = {}
        for field_name in cls.all_fields():
            kwargs[field_name] = getattr(formula_field, field_name)
        return cls(**kwargs)

    def _has_user_defined_values(self, field: "FormulaField") -> bool:
        """
        Returns True if the formula field has any user defined values for the type or
        False if not, so that our formula language can suggest which values could be
        used.

        :param formula_field: The formula field to check if the user has set any values
            for the type.
        :return: True if the user has set any values for the type or False if not.
        """

        from baserow.contrib.database.fields.models import FormulaField

        # if the formula_field exists and the type haven't changed, we don't want to
        # override the user set values with the formula calculated values for the type.
        formula_type = field.array_formula_type or field.formula_type
        if field.id and formula_type == self.type:
            return True
        else:
            # check if any of the user_overridable_formatting_option_fields is different
            # from the field default value, If so, don't override them.
            for field_name in self.user_overridable_formatting_option_fields:
                override_set_by_user = getattr(field, field_name)
                field_attr = getattr(FormulaField, field_name).field
                default_value = None if field_attr.null else field_attr.default
                if override_set_by_user != default_value:
                    return True
        return False

    def new_type_with_user_and_calculated_options_merged(self: T, formula_field):
        """
        Generates a new merged BaserowFormulaType instance from what has been set on the
        formula field and this instance of the type. Fields which are set on
        this types user_overridable_formatting_option_fields will be taken from the
        FormulaField instance if set there, otherwise the values from the type instance
        will be used.

        :param formula_field: The formula field to get any type option overrides set by
            the user from.
        :return: A new merged object of the formula type using values from both the
            instance and if set values also from the formula field.
        """

        kwargs = {}
        source = formula_field if self._has_user_defined_values(formula_field) else self
        for field_name in self.user_overridable_formatting_option_fields:
            kwargs[field_name] = getattr(source, field_name)
        for field_name in self.get_internal_fields():
            kwargs[field_name] = getattr(self, field_name)
        return self.__class__(**kwargs)

    def persist_onto_formula_field(self, formula_field):
        """
        Saves this type onto the provided formula_field instance for later retrieval.
        Sets the attributes on the formula_field required
        for this formula type and unsets all other formula types attributes. Does not
        save the formula_field.

        :param formula_field: The formula field to store the type information onto.
        """

        from baserow.contrib.database.fields.models import FormulaField
        from baserow.contrib.database.formula.types.formula_types import (
            BASEROW_FORMULA_TYPE_ALLOWED_FIELDS,
        )

        field_has_user_defined_values = self._has_user_defined_values(formula_field)

        formula_field.formula_type = self.type
        for attr in BASEROW_FORMULA_TYPE_ALLOWED_FIELDS:
            if attr in self.user_overridable_formatting_option_fields:
                if not field_has_user_defined_values:
                    setattr(formula_field, attr, getattr(self, attr))
            elif attr in self.get_internal_fields():
                setattr(formula_field, attr, getattr(self, attr))
            else:  # unset all attributes unnecessary for this formula type to original
                field_attr = getattr(FormulaField, attr).field
                default_field_value = None if field_attr.null else field_attr.default
                setattr(formula_field, attr, default_field_value)

    def get_baserow_field_instance_and_type(self) -> "tuple[Model, FieldType]":
        from baserow.contrib.database.fields.registries import field_type_registry

        baserow_field_type = field_type_registry.get(self.baserow_field_type)
        field_instance = baserow_field_type.from_baserow_formula_type(self)
        return field_instance, baserow_field_type

    def should_recreate_when_old_type_was(self, old_type: "BaserowFormulaType") -> bool:
        """
        :param old_type: The previous type of a formula field.
        :return: True if the formula field should have it's database column recreated
            given it's old_type.
        """

        return not isinstance(self, type(old_type))

    def wrap_at_field_level(self, expr: "tree.BaserowExpression[BaserowFormulaType]"):
        """
        If a field of this formula type requires any wrapping at the highest level
        do it here.

        :param expr: The calculated and typed expression of this type.
        :return: A new expression with any required extra calculations done at the top
            field level.
        """

        return expr

    def unwrap_at_field_level(self, expr: "tree.BaserowExpression[BaserowFormulaType]"):
        """
        If a field of this formula type requires any unwrapping when referenced then
        do it here.

        :param expr: The calculated and typed expression of this type.
        :return: A new expression with any required extra calculations undone at the top
            field level.
        """

        return expr

    def collapse_many(self, expr: "tree.BaserowExpression[BaserowFormulaType]"):
        """
        Should return an expression which collapses the given expression into a single
        non aggregate value.

        :param expr: An expression containing many rows which needs to be aggregated.
        :return: An expression which collapses the provided aggregate expr into a single
            value.
        """

        return expr

    def try_coerce_to_not_null(
        self, expr: "tree.BaserowExpression[BaserowFormulaValidType]"
    ):
        """
        Tries to coerce the given expression to a not null type. The default
        behavior is to return the expression as is. Override this method if the
        type can be coerced to a not null type or extends
        BaserowFormulaTypeHasEmptyBaserowExpression and has a
        placeholder_empty_baserow_expression method.
        """

        return expr

    def add(
        self,
        add_func_call: "tree.BaserowFunctionCall[UnTyped]",
        arg1: "tree.BaserowExpression[BaserowFormulaValidType]",
        arg2: "tree.BaserowExpression[BaserowFormulaValidType]",
    ) -> "tree.BaserowExpression[BaserowFormulaType]":
        return add_func_call.with_invalid_type(
            f"cannot perform addition on type {arg1.expression_type} and "
            f"{arg2.expression_type}"
        )

    def minus(
        self,
        minus_func_call: "tree.BaserowFunctionCall[UnTyped]",
        arg1: "tree.BaserowExpression[BaserowFormulaValidType]",
        arg2: "tree.BaserowExpression[BaserowFormulaValidType]",
    ) -> "tree.BaserowExpression[BaserowFormulaType]":
        return minus_func_call.with_invalid_type(
            f"cannot perform subtraction on type {arg1.expression_type} and "
            f"{arg2.expression_type}"
        )

    def multiply(
        self,
        multiply_func_call: "tree.BaserowFunctionCall[UnTyped]",
        arg1: "tree.BaserowExpression[BaserowFormulaValidType]",
        arg2: "tree.BaserowExpression[BaserowFormulaValidType]",
    ) -> "tree.BaserowExpression[BaserowFormulaType]":
        return multiply_func_call.with_invalid_type(
            f"cannot perform multiplication on type {arg1.expression_type} and "
            f"{arg2.expression_type}"
        )

    def divide(
        self,
        divide_func_call: "tree.BaserowFunctionCall[UnTyped]",
        arg1: "tree.BaserowExpression[BaserowFormulaValidType]",
        arg2: "tree.BaserowExpression[BaserowFormulaValidType]",
    ) -> "tree.BaserowExpression[BaserowFormulaType]":
        return divide_func_call.with_invalid_type(
            f"cannot perform division on type {arg1.expression_type} and "
            f"{arg2.expression_type}"
        )

    def placeholder_empty_value(self) -> Expression:
        """
        Should be a valid value safe to store in a formula field of this type as a
        placeholder value in an INSERT statement.
        """

        return Value(None)

    def check_if_compatible_with(self, compatible_formula_types: List[str]):
        return self.type in compatible_formula_types

    def __str__(self) -> str:
        return self.type

    def __init__(self, nullable=False, requires_refresh_after_insert=False):
        self.nullable = nullable
        self.requires_refresh_after_insert = requires_refresh_after_insert

    def get_search_expression(self, field, queryset):
        (
            field_instance,
            field_type,
        ) = self.get_baserow_field_instance_and_type()
        # Ensure the fake field_instance can have db_column called on it
        field_instance.id = field.id
        return field_type.get_search_expression(field_instance, queryset)

    def get_search_expression_in_array(self, field, queryset) -> Expression:
        return extract_jsonb_array_values_to_single_string(field, queryset)

    def is_searchable(self, field):
        (
            field_instance,
            field_type,
        ) = self.get_baserow_field_instance_and_type()
        # Ensure the fake field_instance can have db_column called on it
        field_instance.id = field.id
        return field_type.is_searchable(field_instance)

    def parse_filter_value(self, field, model_field, value):
        """
        Use the Baserow field type method where possible to prepare the filter value.
        """

        (
            field_instance,
            field_type,
        ) = self.get_baserow_field_instance_and_type()
        return field_type.parse_filter_value(field_instance, model_field, value)


class BaserowFormulaInvalidType(BaserowFormulaType):
    is_valid = False
    can_order_by = False
    can_group_by = False
    can_have_db_index = False
    comparable_types = []
    limit_comparable_types = []
    type = "invalid"
    baserow_field_type = "text"
    internal_fields = ["error"]

    text_default = ""

    def raise_if_invalid(self):
        raise InvalidFormulaType(self.error)

    def should_recreate_when_old_type_was(self, old_type: "BaserowFormulaType") -> bool:
        return False

    def get_search_expression(self, field, queryset) -> Expression:
        return Value(None)

    def get_search_expression_in_array(self, field, queryset) -> Expression:
        return Value(None)

    def is_searchable(self, field) -> bool:
        return False

    def __init__(self, error: str, **kwargs):
        self.error = error
        super().__init__(**kwargs)


class BaserowFormulaValidType(BaserowFormulaType, abc.ABC):
    is_valid = True
    can_order_by = True

    @property
    @abc.abstractmethod
    def limit_comparable_types(self) -> List[Type["BaserowFormulaValidType"]]:
        pass

    def collapse_many(self, expr: "tree.BaserowExpression[BaserowFormulaType]"):
        from baserow.contrib.database.formula.registries import (
            formula_function_registry,
        )

        if self.item_is_in_nested_value_object_when_in_array:
            func = formula_function_registry.get("array_agg")
        else:
            func = formula_function_registry.get("array_agg_no_nesting")
        return func(expr)

    def collapse_array_of_many(
        self, expr: "tree.BaserowExpression[BaserowFormulaType]"
    ):
        from baserow.contrib.database.formula.registries import (
            formula_function_registry,
        )

        return formula_function_registry.get("array_agg_unnesting")(expr)

    def raise_if_invalid(self):
        pass

    def is_blank(
        self,
        func_call: "tree.BaserowFunctionCall[UnTyped]",
        arg: "tree.BaserowExpression[BaserowFormulaValidType]",
    ) -> "tree.BaserowExpression[BaserowFormulaBooleanType]":
        """
        Returns an expression which evaluates to true if the given expression is
        blank. Different formula types may have different definitions of what is
        blank (e.g. isblank(0) returns True for numbers, False for text ).
        """

        from baserow.contrib.database.formula.types.formula_types import literal

        equal_expr = formula_function_registry.get("equal")
        return equal_expr(
            self.cast_to_text(func_call, arg),
            literal(""),
        )

    def cast_to_text(
        self,
        to_text_func_call: "tree.BaserowFunctionCall[UnTyped]",
        arg: "tree.BaserowExpression[BaserowFormulaValidType]",
    ) -> "tree.BaserowExpression[BaserowFormulaType]":
        """
        Given a expression which is an untyped BaserowToText function call this function
        should return an expression which results in this type being turning into a
        BaserowFormulaTextType.

        :param to_text_func_call: A BaserowToText function call expression where the
            argument is of this type and is required to be turned into a text type.
        :param arg: The typed argument that needs to be turned into a text type.
        :return: A typed BaserowExpression which results in arg turning into a text
            type.
        """

        # We default to not having to do any extra expression wrapping to convert to
        # the text type by just returning the existing to_text func call which by
        # default just does a Cast(arg, output_field=fields.TextField()).
        from baserow.contrib.database.formula.types.formula_types import (
            BaserowFormulaTextType,
        )

        return to_text_func_call.with_valid_type(BaserowFormulaTextType())

    def wrap_at_field_level(self, expr: "tree.BaserowExpression[BaserowFormulaType]"):
        from baserow.contrib.database.formula.registries import (
            formula_function_registry,
        )

        return formula_function_registry.get("error_to_null")(expr)

    def unwrap_at_field_level(self, expr: "tree.BaserowExpression[BaserowFormulaType]"):
        return expr.args[0].with_valid_type(expr.expression_type)

    def count(
        self,
        to_text_func_call: "tree.BaserowFunctionCall[UnTyped]",
        arg: "tree.BaserowExpression[BaserowFormulaValidType]",
    ) -> "tree.BaserowExpression[BaserowFormulaType]":
        """
        Given a expression which is an untyped BaserowCount function call this function
        should return an expression which results in this type being turned into a
        BaserowFormulaNumberType.

        :param to_text_func_call: A BaserowCount function call expression where the
            argument is of this type and is required to be turned into a number type.
        :param arg: The typed argument that needs to be turned into a number type.
        :return: A typed BaserowExpression which results in arg turning into a number
            type.
        """

        from baserow.contrib.database.formula.types.formula_types import (
            BaserowFormulaNumberType,
        )

        return to_text_func_call.with_valid_type(
            BaserowFormulaNumberType(number_decimal_places=0)
        )


UnTyped = type(None)
