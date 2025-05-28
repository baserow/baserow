import abc
import typing
from datetime import datetime, timezone
from decimal import Decimal
from typing import Generic, List, Optional, Tuple, Type, TypeVar

from django.conf import settings
from django.db.models import Model

from baserow.contrib.database.formula.ast import visitors
from baserow.contrib.database.formula.ast.exceptions import (
    InvalidIntLiteralProvided,
    InvalidStringLiteralProvided,
    TooLargeStringLiteralProvided,
)
from baserow.contrib.database.formula.types import formula_type
from baserow.contrib.database.formula.types.type_checker import (
    SingleArgumentTypeChecker,
)
from baserow.core.formula.parser.parser import convert_string_to_string_literal_token
from baserow.core.registry import Instance

if typing.TYPE_CHECKING:
    from baserow.contrib.database.formula.expression_generator.generator import (
        WrappedExpressionWithMetadata,
    )

A = TypeVar("A")
T = TypeVar("T")
R = TypeVar("R")


class BaserowExpression(abc.ABC, Generic[A]):
    """
    The root base class for a BaserowExpression which can be seen as an abstract
    syntax tree of a Baserow Formula.

    For example the formula `concat(field('a'),1+1)` is equivalently represented by the
    following BaserowExpression AST:

    ```
    BaserowFunctionCall(
        BaserowConcat(),
        [
            BaserowFieldReference('a'),
            BaserowFunctionCall(
                BaserowAdd(),
                [
                    BaserowIntegerLiteral(1),
                    BaserowIntegerLiteral(1)
                ]
            )
        ]
    )
    ```

    A BaserowExpression has a generic type parameter A. This indicates the type of
    the additional field `expression_type` attached to every BaserowExpression.
    This allows us to talk about BaserowExpression's as they go through the various
    stages of parsing and typing using the python type system to help us.

    For example, imagine I parse a raw input string and have yet to figure out the types
    of a baserow expression. Then the type of the `expression_type` attached to each
    node in the BaserowExpression tree is None as we don't know it yet. And so we can
    write for the formula `concat('a', 'b')`:


    ```
    # Look at what UnTyped is defined as (its `type(None)`)!
    untyped_expr = BaserowFunctionCall[UnTyped](
        BaserowConcat(),
        [
            BaserowStringLiteral[UnTyped]('a'),
            BaserowStringLiteral[UnTyped]('b')
        ]
    )
    ```

    Pythons type system will now help us as we have used a generic type here and if
    we try to do something with `untyped_expr.expression_type` we will get a nice type
    warning that it is None.

    Now imagine we go through and figure out the types, now we can use the various
    with_type functions defined below to transform an expression into a different
    generically typed form!

    ```
    untyped_expr = BaserowFunctionCall[UnTyped](
        BaserowConcat(),
        [
            BaserowStringLiteral[UnTyped]('a').with_valid_type(
                BaserowFormulaTextType()
            ),
            BaserowStringLiteral[UnTyped]('b').with_valid_type(
                BaserowFormulaTextType()
            )
        ]
    )
    typed_expression = untyped_expr.with_valid_type(BaserowFormulaTextType())
    # Now python knows that typed_expression is of type
    # BaserowExpression[BaserowFormulaType] and so we can safely access it:
    do_thing_with_type(typed_expression.expression_type)
    ```
    """

    def __init__(
        self,
        expression_type: A,
        aggregate=False,
        many=False,
        requires_aggregate_wrapper=False,
    ):
        self.expression_type: A = expression_type
        self.aggregate = aggregate
        self.many = many
        self.requires_aggregate_wrapper = requires_aggregate_wrapper

    @property
    def is_wrapper(self) -> bool:
        """
        A wrapper expression is a function call that needs to be removed in nested
        field references.
        Returns True if the expression is a wrapper expression (e.g 'error_to_nan()').
        Look at `FormulaTypingVisitor.visit_field_reference` for more information.
        """

        return False

    @abc.abstractmethod
    def accept(self, visitor: "visitors.BaserowFormulaASTVisitor[A, T]") -> T:
        pass

    def with_type(self, expression_type: "R") -> "BaserowExpression[R]":
        self.expression_type = expression_type
        return self

    def with_valid_type(
        self,
        expression_type: "formula_type.BaserowFormulaValidType",
        nullable: Optional[bool] = None,
    ) -> "BaserowExpression[formula_type.BaserowFormulaValidType]":
        if nullable is not None:
            expression_type = self.with_nullable(expression_type, nullable)
        return self.with_type(expression_type)

    def with_nullable(
        self, expression_type: "formula_type.BaserowFormulaValidType", nullable: bool
    ) -> "BaserowExpression[formula_type.BaserowFormulaValidType]":
        expression_type.nullable = nullable
        return expression_type

    def with_invalid_type(
        self, error: str
    ) -> "BaserowExpression[formula_type.BaserowFormulaInvalidType]":
        return self.with_type(formula_type.BaserowFormulaInvalidType(error))


class BaserowStringLiteral(BaserowExpression[A]):
    """
    Represents a string literal typed directly into the formula.
    """

    def __init__(self, literal: str, expression_type: A):
        super().__init__(expression_type)

        if not isinstance(literal, str):
            raise InvalidStringLiteralProvided()
        if len(literal) > settings.MAX_FORMULA_STRING_LENGTH:
            raise TooLargeStringLiteralProvided()
        self.literal = literal

    def accept(self, visitor: "visitors.BaserowFormulaASTVisitor[A, T]") -> T:
        return visitor.visit_string_literal(self)

    def __str__(self):
        return convert_string_to_string_literal_token(self.literal, True)


class BaserowIntegerLiteral(BaserowExpression[A]):
    """
    Represents a literal integer typed into the formula.
    """

    def __init__(self, literal: int, expression_type: A):
        super().__init__(expression_type)

        if not isinstance(literal, int):
            raise InvalidIntLiteralProvided()
        self.literal = literal

    def accept(self, visitor: "visitors.BaserowFormulaASTVisitor[A, T]") -> T:
        return visitor.visit_int_literal(self)

    def __str__(self):
        return str(self.literal)


class BaserowDecimalLiteral(BaserowExpression[A]):
    """
    Represents a literal decimal typed into the formula.
    """

    def __init__(self, literal: Decimal, expression_type: A):
        super().__init__(expression_type)
        self.literal = literal

    def num_decimal_places(self):
        return -self.literal.as_tuple().exponent

    def accept(self, visitor: "visitors.BaserowFormulaASTVisitor[A, T]") -> T:
        return visitor.visit_decimal_literal(self)

    def __str__(self):
        return str(self.literal)


class BaserowBooleanLiteral(BaserowExpression[A]):
    """
    Represents a literal boolean typed into the formula.
    """

    def __init__(self, literal: bool, expression_type: A):
        super().__init__(expression_type)
        self.literal = literal

    def accept(self, visitor: "visitors.BaserowFormulaASTVisitor[A, T]") -> T:
        return visitor.visit_boolean_literal(self)

    def __str__(self):
        return "true" if self.literal else "false"


class BaserowFieldReference(BaserowExpression[A]):
    """
    Represents a reference to a field with the same name as the referenced_field_name.
    """

    def __init__(
        self,
        referenced_field_name: str,
        target_field: Optional[str],
        expression_type: A,
    ):
        many = target_field is not None
        super().__init__(expression_type, many=many, aggregate=many)
        self.referenced_field_name = referenced_field_name
        # If set target_field is a field in another table to lookup via the
        # referenced_field_name.
        self.target_field = target_field
        self.requires_refresh_after_insert = bool(
            expression_type and expression_type.requires_refresh_after_insert
        )

    def accept(self, visitor: "visitors.BaserowFormulaASTVisitor[A, T]") -> T:
        return visitor.visit_field_reference(self)

    def is_lookup(self):
        return self.target_field is not None

    def __str__(self):
        escaped_name = convert_string_to_string_literal_token(
            self.referenced_field_name, True
        )
        if self.target_field is None:
            return f"field({escaped_name})"
        else:
            escaped_lookup = convert_string_to_string_literal_token(
                self.target_field, True
            )
            return f"lookup({escaped_name},{escaped_lookup})"


class ArgCountSpecifier(abc.ABC):
    """
    A base class defining a checker which returns if the number of arguments given to
    a function is correct or not.
    """

    def __init__(self, count):
        self.count = count

    @abc.abstractmethod
    def test(self, num_args: int):
        """
        Should return if the provided num_args matches this ArgCountSpecifier.
        For example if you were extending this class to create a ArgCountSpecifier that
        required the num_args to be less than a fixed number, then here you would check
        return num_args < fixed_number.
        :param num_args: The number of args being provided.
        :return: Whether or not the number of args meets this specification.
        """

        pass

    @abc.abstractmethod
    def __str__(self):
        """
        Should be implemented to explain how to meet this specification in a human
        readable string format.
        """

        pass


class BaserowExpressionContext:
    def __init__(self, model: Type[Model], model_instance: Optional[Model]):
        self.model = model
        self.model_instance = model_instance
        try:
            # TODO: rename to workspace
            self.group = model.get_root()
        except ValueError:
            # when creating a snapshot, the application does not have a root, but it's
            # not mandatory to have one
            self.group = None

    def get_utc_now(self):
        # Inside a workspace, we want to use the workspace value to keep all the
        # formulas in sync. If the workspace is not set as during a snapshot, we can use
        # just the current time to ensure rows have a value.
        if self.group:
            return self.group.get_now_or_set_if_null()
        else:
            return datetime.now(tz=timezone.utc)


class BaserowFunctionCall(BaserowExpression[A]):
    """
    Represents a function call with arguments to the function defined by function_def.
    """

    def __init__(
        self,
        function_def: "BaserowFunctionDefinition",
        args: List[BaserowExpression[A]],
        expression_type: A,
        requires_aggregate_wrapper=False,
    ):
        if function_def.aggregate:
            many = False
            aggregate = True
        else:
            many = any(a.many for a in args)
            aggregate = any(a.aggregate for a in args)

        super().__init__(
            expression_type,
            many=many,
            aggregate=aggregate,
            requires_aggregate_wrapper=requires_aggregate_wrapper,
        )

        self.function_def = function_def
        self.args = args

    @property
    def is_wrapper(self) -> bool:
        return self.function_def.is_wrapper

    def accept(self, visitor: "visitors.BaserowFormulaASTVisitor[A, T]") -> T:
        return visitor.visit_function_call(self)

    def type_function_given_typed_args(
        self,
        args: "List[BaserowExpression[formula_type.BaserowFormulaType]]",
    ) -> "BaserowExpression[formula_type.BaserowFormulaType]":
        return self.function_def.type_function_given_typed_args(
            args, self.with_args(args)
        )

    def type_function_given_valid_args(
        self,
        args: "List[BaserowExpression[formula_type.BaserowFormulaValidType]]",
    ) -> "BaserowExpression[formula_type.BaserowFormulaType]":
        return self.function_def.type_function_given_valid_args(
            args, self.with_args(args)
        )

    def to_django_expression_given_args(
        self,
        args: List["WrappedExpressionWithMetadata"],
        context: BaserowExpressionContext,
    ) -> "WrappedExpressionWithMetadata":
        return self.function_def.to_django_expression_given_args(args, context)

    def check_arg_type_valid(
        self,
        i: int,
        typed_arg: "BaserowExpression[formula_type.BaserowFormulaType]",
        all_typed_args: "List[BaserowExpression[formula_type.BaserowFormulaType]]",
    ) -> "BaserowExpression[formula_type.BaserowFormulaType]":
        return self.function_def.check_arg_type_valid(i, typed_arg, all_typed_args)

    def with_args(self, new_args) -> "BaserowFunctionCall[A]":
        """
        :param new_args: The arguments to use in the newly constructed function call.
        :return: A new BaserowFunctionCall to the same function_def but with replaced
            arguments.
        """

        return BaserowFunctionCall(self.function_def, new_args, self.expression_type)

    def __str__(self):
        args_string = ",".join([str(a) for a in self.args])
        return f"{self.function_def.type}({args_string})"


class BaserowFunctionDefinition(Instance, abc.ABC):
    """
    A registrable instance which defines a function for use in the Baserow Formula
    language. You most likely want to instead work with one of the simpler to use
    abstract sub classes of this class, depending on how many arguments your function
    takes:
    - OneArgumentBaserowFunction
    - TwoArgumentBaserowFunction
    - ThreeArgumentBaserowFunction
    """

    is_wrapper = False
    try_coerce_nullable_args_to_not_null: bool = True

    @property
    @abc.abstractmethod
    def type(self) -> str:
        """
        :return: The unique name case insensitive name for this function. Users will
            call this function using the name defined here.
        """

        pass

    @property
    def aggregate(self) -> bool:
        """
        :return: If this function is an aggregate one which collapses a many expression
            down to a single value.
        """

        return False

    @property
    def operator(self) -> Optional[str]:
        """
        :return: If this function definition is used by an operator return the operators
             text representation here.
        """

        return None

    @property
    @abc.abstractmethod
    def num_args(self) -> ArgCountSpecifier:
        """
        :return: An ArgCountSpecifier which defines how many arguments this function
            supports.
        """

        pass

    @property
    @abc.abstractmethod
    def arg_types(self) -> "formula_type.BaserowArgumentTypeChecker":
        """
        :return: An argument type checker which checks all arguments provided to this
            function have valid types.
        """

        pass

    @property
    def requires_refresh_after_insert(self) -> bool:
        """
        :return: True if by using this function to have it's value calculated properly
            a row must first be inserted and then refreshed.
        """

        return False

    @abc.abstractmethod
    def type_function_given_valid_args(
        self,
        args: "List[BaserowExpression[formula_type.BaserowFormulaValidType]]",
        expression: "BaserowFunctionCall[formula_type.UnTyped]",
    ) -> "BaserowExpression[formula_type.BaserowFormulaType]":
        """
        Given a list of arguments extracted from the function call expression, already
        typed and checked by the self.arg_types property should calculate and return
        a typed BaserowExpression for this function.

        :param args: The typed and valid arguments taken from expression.
        :param expression: A func call expression for this function type which is
            untyped.
        :return: A typed and possibly transformed or changed BaserowExpression for this
            function call.
        """

        pass

    @abc.abstractmethod
    def to_django_expression_given_args(
        self,
        args: List["WrappedExpressionWithMetadata"],
        context: BaserowExpressionContext,
    ) -> "WrappedExpressionWithMetadata":
        """
        Given the args already converted to Django Expressions should return a Django
        Expression which calculates the result of a call to this function.

        Will only be called if all the args have passed the type check and the function
        itself was typed with a BaserowValidType.

        :param model: The model the expression is being generated for.
        :param args: The already converted to Django expression args.
        :param model_instance: If set then the model instance which is being inserted
            or if False then the django expression is for an update statement.
        :return: A Django Expression which calculates the result of this function.
        """

        pass

    def type_function_given_typed_args(
        self,
        typed_args: "List[BaserowExpression[formula_type.BaserowFormulaType]]",
        expression: "BaserowFunctionCall[formula_type.UnTyped]",
    ) -> "BaserowExpression[formula_type.BaserowFormulaType]":
        """
        Given the already typed arguments for a func_call to a function of this
        definition this function will check the type of each argument against the
        arg_types property. If they all pass the type check then the user implemented
        type_function_given_valid_args will be called. If they don't a
        BaserowInvalidType will be returned containing a relevant error message.

        :param typed_args: The typed but not checked argument BaserowExpressions.
        :param expression: The func_call expression which contains the typed_args but
            is not yet typed as we first need to type and check the args.
        :return: A fully typed and possibly transformed BaserowExpression which
            implements a call to this function.
        """

        valid_args: "List[BaserowExpression[formula_type.BaserowFormulaValidType]]" = (
            list()
        )
        invalid_results: "List[Tuple[int, formula_type.BaserowFormulaInvalidType]]" = []
        for i, typed_arg in enumerate(typed_args):
            arg_type = typed_arg.expression_type

            if isinstance(arg_type, formula_type.BaserowFormulaInvalidType):
                invalid_results.append((i, arg_type))
            else:
                checked_typed_arg = expression.check_arg_type_valid(
                    i, typed_arg, typed_args
                )
                if isinstance(
                    checked_typed_arg.expression_type,
                    formula_type.BaserowFormulaInvalidType,
                ):
                    invalid_results.append((i, checked_typed_arg.expression_type))
                else:
                    # Must be a valid type but the intellij type checker isn't so smart
                    # noinspection PyTypeChecker
                    valid_args.append(checked_typed_arg)
        if len(invalid_results) > 0:
            message = ", ".join([t.error for _, t in invalid_results])
            return expression.with_invalid_type(message)
        else:
            return self.type_function_given_valid_args(valid_args, expression)

    def call_and_type_with_args(
        self,
        args: "List[BaserowExpression[formula_type.BaserowFormulaType]]",
    ) -> "BaserowFunctionCall[formula_type.BaserowFormulaType]":
        func_call = BaserowFunctionCall[formula_type.UnTyped](self, args, None)
        return func_call.type_function_given_typed_args(args)

    def check_arg_type_valid(
        self,
        arg_index: int,
        typed_arg: "BaserowExpression[formula_type.BaserowFormulaType]",
        all_typed_args: "List[BaserowExpression[formula_type.BaserowFormulaType]]",
    ) -> "BaserowExpression[formula_type.BaserowFormulaType]":
        """
        Checks if the typed argument at arg_index is a valid type using the
        self.arg_types type checker.

        :param arg_index: The 0 based index for this argument.
        :param typed_arg: The already typed but not checked argument expression.
        :param all_typed_args: All other typed but not checked arguments for this
            function call.
        :return: The updated typed expression for this argument (the same type if it
            passes the check, an invalid type if it does not pass).
        """

        if callable(self.arg_types):
            arg_type_checkers = self.arg_types(
                arg_index, [t.expression_type for t in all_typed_args]
            )
        else:
            arg_type_checkers = self.arg_types[arg_index]

        expression_type = typed_arg.expression_type
        valid_type_names = []
        for checker in arg_type_checkers:
            if isinstance(checker, SingleArgumentTypeChecker):
                if checker.check(arg_index, typed_arg):
                    return typed_arg
                else:
                    valid_type_names.append(
                        checker.invalid_message(arg_index, typed_arg)
                    )
            elif isinstance(expression_type, checker):
                return typed_arg
            else:
                valid_type_names.append(checker.type)

        expression_type_name = expression_type.type
        if len(valid_type_names) == 1:
            postfix = f"the only usable type for this argument is {valid_type_names[0]}"
        elif len(valid_type_names) == 0:
            postfix = f"there are no possible types usable here"
        else:
            postfix = (
                f"the only usable types for this argument are "
                f"{','.join(valid_type_names)}"
            )

        return typed_arg.with_invalid_type(
            f"argument number {arg_index+1} given to {self} was of type "
            f"{expression_type_name} but {postfix}"
        )

    def __str__(self):
        if self.operator is None:
            return "function " + self.type
        else:
            return "operator " + self.operator

    def __eq__(self, other):
        if type(other) is type(self):
            return self.type == other.type
        else:
            return False

    def __hash__(self):
        return hash(self.type)
