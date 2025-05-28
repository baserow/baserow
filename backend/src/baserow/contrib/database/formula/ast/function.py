import abc
from datetime import timedelta
from typing import List, Type

from django.db.models import (
    DecimalField,
    Expression,
    ExpressionWrapper,
    Model,
    OuterRef,
    QuerySet,
    Subquery,
    Value,
)
from django.db.models.fields import DurationField
from django.db.models.functions import Coalesce

from baserow.contrib.database.formula.ast.tree import (
    ArgCountSpecifier,
    BaserowExpression,
    BaserowExpressionContext,
    BaserowFunctionCall,
    BaserowFunctionDefinition,
)
from baserow.contrib.database.formula.expression_generator.django_expressions import (
    AndExpr,
)
from baserow.contrib.database.formula.expression_generator.generator import (
    WrappedExpressionWithMetadata,
)
from baserow.contrib.database.formula.types.formula_type import (
    BaserowFormulaType,
    BaserowFormulaValidType,
    UnTyped,
)
from baserow.contrib.database.formula.types.type_checker import (
    BaserowArgumentTypeChecker,
    BaserowSingleArgumentTypeChecker,
)


class FixedNumOfArgs(ArgCountSpecifier):
    def __str__(self):
        if self.count == 1:
            plural = ""
        else:
            plural = "s"
        return f"exactly {self.count} argument{plural}"

    def test(self, num_args):
        return self.count == num_args


class NumOfArgsGreaterThan(ArgCountSpecifier):
    def __str__(self):
        return f"more than {self.count} arguments"

    def test(self, num_args):
        return self.count < num_args


class NumOfArgsBetween(ArgCountSpecifier):
    def __init__(self, min_count, max_count, inclusive=True):
        self.min_count = min_count
        self.max_count = max_count
        self.inclusive = inclusive

    def __str__(self):
        return (
            f"more than {self.min_count} and less than {self.max_count} "
            f"(inclusive={self.inclusive}) arguments"
        )

    def test(self, num_args):
        if self.inclusive:
            return self.min_count <= num_args <= self.max_count
        else:
            return self.min_count < num_args < self.max_count


class ToDjangoExpressionGivenArgsMixin:
    def to_django_expression_given_args(
        self,
        args: List["WrappedExpressionWithMetadata"],
        context: BaserowExpressionContext,
    ) -> "WrappedExpressionWithMetadata":
        expr = WrappedExpressionWithMetadata.from_args(
            self.to_django_expression(*[arg.expression for arg in args]), args
        )
        if self.aggregate:
            return aggregate_wrapper(expr, context.model)
        else:
            return expr


class ZeroArgumentBaserowFunction(
    ToDjangoExpressionGivenArgsMixin, BaserowFunctionDefinition
):
    """
    A helper sub type of a BaserowFunctionDefinition that lets the
    user talk specifically about a func with no arguments when implementing. Without
    this normal classes implementing BaserowFunctionDefinition need to faff
    about accessing argument lists etc.
    """

    @property
    def arg_types(self) -> BaserowArgumentTypeChecker:
        return []

    @property
    def num_args(self) -> ArgCountSpecifier:
        return FixedNumOfArgs(0)

    @abc.abstractmethod
    def type_function(
        self,
        func_call: BaserowFunctionCall[UnTyped],
    ) -> BaserowExpression[BaserowFormulaType]:
        """
        Override this function to type and optionally transform an untyped function
        call to this function def.

        You can perform any logic you require here and return entirely different or
        transformed typed expressions. However by default most
        of the time if your function doesn't need to do different things based on
        the types of it's arguments all you need to do is something like:
        ```
        return func_call.with_valid_type(INSERT VALID TYPE OF FUNC HERE)
        ```

        :param func_call: An untyped function call to this function which needs typing.
        :return: A typed BaserowExpression, most probably just the original func_call
            but with a type, but any expression could be returned here.
        """

        pass

    @abc.abstractmethod
    def to_django_expression(self) -> Expression:
        """
        Override this function to return a Django Expression which calculates the result
        of this function.
        Only will be called if all arguments passed the type check
        and a valid type for the function has been returned from type_function.

        :return: A Django Expression which when evaluated calculates the results of this
            function call.
        """

        pass

    def type_function_given_valid_args(
        self,
        args: List[BaserowExpression[BaserowFormulaValidType]],
        func_call: BaserowFunctionCall[UnTyped],
    ) -> BaserowExpression[BaserowFormulaType]:
        return self.type_function(func_call)

    def __call__(self) -> BaserowFunctionCall[BaserowFormulaType]:
        return self.call_and_type_with_args([])


class OneArgumentBaserowFunction(
    ToDjangoExpressionGivenArgsMixin, BaserowFunctionDefinition
):
    """
    A helper sub type of a BaserowFunctionDefinition that lets the
    user talk specifically about the single argument in a one arg func when implementing
    . Without this normal classes implementing BaserowFunctionDefinition need to faff
    about accessing argument lists etc.
    """

    aggregate = False

    @property
    @abc.abstractmethod
    def arg_type(self) -> BaserowSingleArgumentTypeChecker:
        """
        Override this property to set the required argument type for the single argument
        provided to this function. Only when the argument meets the type requirement
        will type_function be called with the argument that matches.

        :return: A BaserowSingleArgumentTypeChecker
        """

        pass

    @property
    def arg_types(self) -> BaserowArgumentTypeChecker:
        return [self.arg_type]

    @property
    def num_args(self) -> ArgCountSpecifier:
        return FixedNumOfArgs(1)

    @abc.abstractmethod
    def type_function(
        self,
        func_call: BaserowFunctionCall[UnTyped],
        arg: BaserowExpression[BaserowFormulaValidType],
    ) -> BaserowExpression[BaserowFormulaType]:
        """
        Override this function to type and optionally transform an untyped function
        call to this function def. The single argument has already been type checked
        according to the self.arg_type property, this method will only be called if it
        matches.

        You can perform any logic you require here and return entirely different or
        transformed typed expressions based on the arguments. However by default most
        of the time if your function doesn't need to do different things based on
        the types of it's arguments all you need to do is something like:
        ```
        return func_call.with_valid_type(INSERT VALID TYPE OF FUNC HERE)
        ```

        :param func_call: An untyped function call to this function which needs typing.
        :param arg: The valid typed single argument from func_call provided already
            extracted from func_call for you to inspect.
        :return: A typed BaserowExpression, most probably just the original func_call
            but with a type, but any expression could be returned here.
        """

        pass

    @abc.abstractmethod
    def to_django_expression(self, arg: Expression) -> Expression:
        """
        Override this function to return a Django Expression which calculates the result
        of this function given that the single arg has already been converted to a
        Django Expression. Only will be called if all arguments passed the type check
        and a valid type for the function has been returned from type_function.

        :param arg: The already converted arg expression to use.
        :return: A Django Expression which when evaluated calculates the results of this
            function call.
        """

        pass

    def type_function_given_valid_args(
        self,
        args: List[BaserowExpression[BaserowFormulaValidType]],
        func_call: BaserowFunctionCall[UnTyped],
    ) -> BaserowExpression[BaserowFormulaType]:
        arg = args[0]

        return self.type_function(func_call, arg)

    def __call__(
        self, arg: BaserowExpression[BaserowFormulaType]
    ) -> BaserowFunctionCall[BaserowFormulaType]:
        return self.call_and_type_with_args([arg])


def aggregate_wrapper(
    expr_with_metadata: WrappedExpressionWithMetadata,
    model: Type[Model],
) -> WrappedExpressionWithMetadata:
    """
    Returns a wrapped expression with metadata which wraps the given expression
    in a subquery. This is useful for BaserowFunctionDefinitions which need to
    aggregate the results over a model.
    """

    subquery = construct_aggregate_wrapper_queryset(expr_with_metadata, model)
    expr: Expression = Subquery(subquery)

    output_field = expr_with_metadata.expression.output_field

    # if the output field type is a number, return 0 instead of null
    if isinstance(output_field, DecimalField):
        expr = Coalesce(expr, Value(0), output_field=output_field)
    elif isinstance(output_field, DurationField):
        expr = Coalesce(expr, timedelta(hours=0), output_field=output_field)

    return WrappedExpressionWithMetadata(
        ExpressionWrapper(expr, output_field=output_field)
    )


def aggregate_expr_with_metadata_filters(
    expr_with_metadata: WrappedExpressionWithMetadata,
) -> Expression:
    """
    Combines all the aggregate filters on the expression into a single filter.
    This function is called before aggregating the expression.

    :param expr_with_metadata: The wrapped expression with metadata to
        aggregate.
    """

    aggregate_filters = expr_with_metadata.aggregate_filters
    combined_filter: Expression = Value(True)
    if len(aggregate_filters) > 0:
        for f in aggregate_filters:
            combined_filter = AndExpr(combined_filter, f)
    return combined_filter


def construct_not_null_filters_for_inner_join(pre_annotations):
    """
    Constructs a dictionary of filters which enforce that each filtered relation
    is not null so django generates us inner joins.

    :param pre_annotations: The pre annotations to construct the filters from.
    :return: A dictionary of filters.
    """

    return {key + "__isnull": False for key in pre_annotations}


def construct_aggregate_wrapper_queryset(
    expr_with_metadata: WrappedExpressionWithMetadata,
    model: Type[Model],
    result_key="result",
) -> QuerySet:
    """
    Constructs a queryset which wraps the given expression. It's meant to be used
    in conjunction with aggregate_wrapper, or to be used directly in a subquery.
    """

    # We need to enforce that each filtered relation is not null so django generates us
    # inner joins.
    not_null_filters_for_inner_join = construct_not_null_filters_for_inner_join(
        expr_with_metadata.pre_annotations
    )

    aggregate_filters = aggregate_expr_with_metadata_filters(expr_with_metadata)

    qs = model.objects_and_trash.annotate(**expr_with_metadata.pre_annotations)

    return (
        qs.filter(
            aggregate_filters, id=OuterRef("id"), **not_null_filters_for_inner_join
        )
        .values("id")
        .annotate(**{result_key: expr_with_metadata.expression})
        .order_by()
        .values(result_key)
    )


class TwoArgumentBaserowFunction(
    ToDjangoExpressionGivenArgsMixin, BaserowFunctionDefinition
):
    """
    A helper sub type of a BaserowFunctionDefinition that lets the
    user talk specifically about the two arguments in a two arg func when implementing.
    Without this normal classes implementing BaserowFunctionDefinition need to faff
    about accessing argument lists etc.
    """

    aggregate = False

    @property
    @abc.abstractmethod
    def arg1_type(self) -> BaserowSingleArgumentTypeChecker:
        """
        Override this property to set the required argument type for the first arg
        provided to this function. Only when all arguments meet the type requirements
        defined in the argX_type properties will type_function be called.


        :return: A BaserowSingleArgumentTypeChecker
        """

        pass

    @property
    @abc.abstractmethod
    def arg2_type(self) -> BaserowSingleArgumentTypeChecker:
        """
        Override this property to set the required argument type for the second arg
        provided to this function. Only when all arguments meet the type requirements
        defined in the argX_type properties will type_function be called.

        :return: A BaserowSingleArgumentTypeChecker
        """

        pass

    @property
    def arg_types(self) -> BaserowArgumentTypeChecker:
        return [self.arg1_type, self.arg2_type]

    @property
    def num_args(self) -> ArgCountSpecifier:
        return FixedNumOfArgs(2)

    @abc.abstractmethod
    def type_function(
        self,
        func_call: BaserowFunctionCall[UnTyped],
        arg1: BaserowExpression[BaserowFormulaValidType],
        arg2: BaserowExpression[BaserowFormulaValidType],
    ) -> BaserowExpression[BaserowFormulaType]:
        """
        Override this function to type and optionally transform an untyped function
        call to this function def. The arguments have already been type checked
        according to the self.arg1_type and self.arg2_type properties this method will
        only be called if they match.

        You can perform any logic you require here and return entirely different or
        transformed typed expressions based on the arguments. However by default most
        of the time if your function doesn't need to do different things based on
        the types of it's arguments all you need to do is something like:
        ```
        return func_call.with_valid_type(INSERT VALID TYPE OF FUNC HERE)
        ```

        :param func_call: An untyped function call to this function which needs typing.
        :param arg1: The valid typed first argument from func_call provided already
            extracted from func_call for you to inspect.
        :param arg2: The valid typed second argument from func_call provided already
            extracted from func_call for you to inspect.
        :return: A typed BaserowExpression, most probably just the original func_call
            but with a type, but any expression could be returned here.
        """

        pass

    @abc.abstractmethod
    def to_django_expression(self, arg1: Expression, arg2: Expression) -> Expression:
        """
        Override this function to return a Django Expression which calculates the result
        of this function given that the args have already been converted to
        Django Expressions. Only will be called if all arguments passed the type check
        and a valid type for the function has been returned from type_function.

        :param arg1: The already converted first arg expression to use.
        :param arg2: The already converted second arg expression to use.
        :return: A Django Expression which when evaluated calculates the results of this
            function call.
        """

        pass

    def type_function_given_valid_args(
        self,
        args: List[BaserowExpression[BaserowFormulaValidType]],
        func_call: BaserowFunctionCall[UnTyped],
    ) -> BaserowExpression[BaserowFormulaType]:
        return self.type_function(func_call, args[0], args[1])

    def __call__(
        self,
        arg1: BaserowExpression[BaserowFormulaType],
        arg2: BaserowExpression[BaserowFormulaType],
    ) -> BaserowFunctionCall[BaserowFormulaType]:
        return self.call_and_type_with_args([arg1, arg2])


class ThreeArgumentBaserowFunction(
    ToDjangoExpressionGivenArgsMixin, BaserowFunctionDefinition
):
    @property
    def arg_types(self) -> BaserowArgumentTypeChecker:
        return [self.arg1_type, self.arg2_type, self.arg3_type]

    @property
    @abc.abstractmethod
    def arg1_type(self) -> BaserowSingleArgumentTypeChecker:
        """
        Override this property to set the required argument type for the first arg
        provided to this function. Only when all arguments meet the type requirements
        defined in the argX_type properties will type_function be called.

        :return: A BaserowSingleArgumentTypeChecker
        """

        pass

    @property
    @abc.abstractmethod
    def arg2_type(self) -> BaserowSingleArgumentTypeChecker:
        """
        Override this property to set the required argument type for the second arg
        provided to this function. Only when all arguments meet the type requirements
        defined in the argX_type properties will type_function be called.

        :return: A BaserowSingleArgumentTypeChecker
        """

        pass

    @property
    @abc.abstractmethod
    def arg3_type(self) -> BaserowSingleArgumentTypeChecker:
        """
        Override this property to set the required argument type for the third arg
        provided to this function. Only when all arguments meet the type requirements
        defined in the argX_type properties will type_function be called.

        :return: A BaserowSingleArgumentTypeChecker
        """

        pass

    @property
    def num_args(self) -> ArgCountSpecifier:
        return FixedNumOfArgs(3)

    @abc.abstractmethod
    def type_function(
        self,
        func_call: BaserowFunctionCall[UnTyped],
        arg1: BaserowExpression[BaserowFormulaValidType],
        arg2: BaserowExpression[BaserowFormulaValidType],
        arg3: BaserowExpression[BaserowFormulaValidType],
    ) -> BaserowExpression[BaserowFormulaType]:
        """
        Override this function to type and optionally transform an untyped function
        call to this function def. The arguments have already been type checked
        according to the self.arg1_type, self.arg2_type and self.arg3_type properties
        this method will only be called if they all match.

        You can perform any logic you require here and return entirely different or
        transformed typed expressions based on the arguments. However by default most
        of the time if your function doesn't need to do different things based on
        the types of it's arguments all you need to do is something like:
        ```
        return func_call.with_valid_type(INSERT VALID TYPE OF FUNC HERE)
        ```

        :param func_call: An untyped function call to this function which needs typing.
        :param arg1: The valid typed first argument from func_call provided already
            extracted from func_call for you to inspect.
        :param arg2: The valid typed second argument from func_call provided already
            extracted from func_call for you to inspect.
        :param arg3: The valid typed third argument from func_call provided already
            extracted from func_call for you to inspect.
        :return: A typed BaserowExpression, most probably just the original func_call
            but with a type, but any expression could be returned here.
        """

        pass

    @abc.abstractmethod
    def to_django_expression(
        self, arg1: Expression, arg2: Expression, arg3: Expression
    ) -> Expression:
        """
        Override this function to return a Django Expression which calculates the result
        of this function given that the args have already been converted to
        Django Expressions. Only will be called if all arguments passed the type check
        and a valid type for the function has been returned from type_function.

        :param arg1: The already converted first arg expression to use.
        :param arg2: The already converted second arg expression to use.
        :param arg3: The already converted third arg expression to use.
        :return: A Django Expression which when evaluated calculates the results of this
            function call.
        """

        pass

    def type_function_given_valid_args(
        self,
        args: List[BaserowExpression[BaserowFormulaValidType]],
        func_call: BaserowFunctionCall[UnTyped],
    ) -> BaserowExpression[BaserowFormulaType]:
        return self.type_function(func_call, args[0], args[1], args[2])

    def __call__(
        self,
        arg1: BaserowExpression[BaserowFormulaType],
        arg2: BaserowExpression[BaserowFormulaType],
        arg3: BaserowExpression[BaserowFormulaType],
    ) -> BaserowFunctionCall[BaserowFormulaType]:
        return self.call_and_type_with_args([arg1, arg2, arg3])


class CollapseManyBaserowFunction:
    """
    Just a helper class to make it easier to define a function that collapses a
    list of arguments into an array of elements.
    """
