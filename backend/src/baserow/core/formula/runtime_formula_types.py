import operator
import random
import uuid
from functools import reduce
from typing import Optional
from zoneinfo import ZoneInfo

from django.utils import timezone

from baserow.core.formula.argument_types import (
    AddableBaserowRuntimeFormulaArgumentType,
    BooleanBaserowRuntimeFormulaArgumentType,
    DateTimeBaserowRuntimeFormulaArgumentType,
    DictBaserowRuntimeFormulaArgumentType,
    NumberBaserowRuntimeFormulaArgumentType,
    SubtractableBaserowRuntimeFormulaArgumentType,
    TextBaserowRuntimeFormulaArgumentType,
)
from baserow.core.formula.registries import RuntimeFormulaFunction
from baserow.core.formula.types import FormulaArg, FormulaArgs, FormulaContext
from baserow.core.formula.validator import ensure_string


class RuntimeConcat(RuntimeFormulaFunction):
    type = "concat"

    def validate_type_of_args(self, args) -> Optional[FormulaArg]:
        arg_type = AddableBaserowRuntimeFormulaArgumentType()
        return next(
            (arg for arg in args if not arg_type.test(arg)),
            None,
        )

    def validate_number_of_args(self, args):
        return len(args) > 1

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return "".join([ensure_string(a) for a in args])


class RuntimeGet(RuntimeFormulaFunction):
    type = "get"
    args = [TextBaserowRuntimeFormulaArgumentType()]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return context[args[0]]


class RuntimeAdd(RuntimeFormulaFunction):
    type = "add"

    def validate_type_of_args(self, args) -> Optional[FormulaArg]:
        arg_type = AddableBaserowRuntimeFormulaArgumentType()
        return next(
            (arg for arg in args if not arg_type.test(arg)),
            None,
        )

    def validate_number_of_args(self, args):
        return len(args) >= 1

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return reduce(operator.add, args)


class RuntimeMinus(RuntimeFormulaFunction):
    type = "minus"

    def validate_type_of_args(self, args) -> Optional[FormulaArg]:
        arg_type = SubtractableBaserowRuntimeFormulaArgumentType()
        return next(
            (arg for arg in args if not arg_type.test(arg)),
            None,
        )

    def validate_number_of_args(self, args):
        return len(args) > 1

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return reduce(operator.sub, args)


class RuntimeMultiply(RuntimeFormulaFunction):
    type = "multiply"
    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def validate_number_of_args(self, args):
        return len(args) == 2

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] * args[1]


class RuntimeDivide(RuntimeFormulaFunction):
    type = "divide"
    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def validate_number_of_args(self, args):
        return len(args) == 2

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] / args[1]


class RuntimeEqual(RuntimeFormulaFunction):
    type = "equal"
    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def validate_number_of_args(self, args):
        return len(args) == 2

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] == args[1]


class RuntimeNotEqual(RuntimeFormulaFunction):
    type = "not_equal"
    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def validate_number_of_args(self, args):
        return len(args) == 2

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] != args[1]


class RuntimeGreaterThan(RuntimeFormulaFunction):
    type = "greater_than"
    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def validate_number_of_args(self, args):
        return len(args) == 2

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] > args[1]


class RuntimeLessThan(RuntimeFormulaFunction):
    type = "less_than"
    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def validate_number_of_args(self, args):
        return len(args) == 2

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] < args[1]


class RuntimeGreaterThanOrEqual(RuntimeFormulaFunction):
    type = "greater_than_or_equal"
    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def validate_number_of_args(self, args):
        return len(args) == 2

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] >= args[1]


class RuntimeLessThanOrEqual(RuntimeFormulaFunction):
    type = "less_than_or_equal"
    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def validate_number_of_args(self, args):
        return len(args) == 2

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] <= args[1]


class RuntimeUpper(RuntimeFormulaFunction):
    type = "upper"

    args = [TextBaserowRuntimeFormulaArgumentType()]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0].upper()


class RuntimeLower(RuntimeFormulaFunction):
    type = "lower"

    args = [TextBaserowRuntimeFormulaArgumentType()]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0].lower()


class RuntimeCapitalize(RuntimeFormulaFunction):
    type = "capitalize"

    args = [TextBaserowRuntimeFormulaArgumentType()]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0].capitalize()


class RuntimeRound(RuntimeFormulaFunction):
    type = "round"

    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        # Default to 2 places
        decimal_places = 2

        if len(args) == 2:
            # Avoid negative numbers
            decimal_places = max(args[1], 0)

        return round(args[0], decimal_places)


class RuntimeIsEven(RuntimeFormulaFunction):
    type = "is_even"

    args = [NumberBaserowRuntimeFormulaArgumentType()]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] % 2 == 0


class RuntimeIsOdd(RuntimeFormulaFunction):
    type = "is_odd"

    args = [NumberBaserowRuntimeFormulaArgumentType()]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] % 2 != 0


class RuntimeDateTimeFormat(RuntimeFormulaFunction):
    type = "datetime_format"

    args = [
        DateTimeBaserowRuntimeFormulaArgumentType(),
        TextBaserowRuntimeFormulaArgumentType(),
        TextBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        tz_name = None
        tz_format = "%Y-%m-%d %H:%M:%S"

        if len(args) == 3:
            tz_name = args[2]
            tz_format = args[1]
        elif len(args) == 2:
            tz_format = args[1]

        if tz_name:
            return args[0].replace(tzinfo=ZoneInfo(tz_name)).strftime(tz_format)

        return args[0].strftime(tz_format)


class RuntimeDay(RuntimeFormulaFunction):
    type = "day"

    args = [DateTimeBaserowRuntimeFormulaArgumentType()]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0].day


class RuntimeMonth(RuntimeFormulaFunction):
    type = "month"

    args = [DateTimeBaserowRuntimeFormulaArgumentType()]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0].month


class RuntimeYear(RuntimeFormulaFunction):
    type = "year"

    args = [DateTimeBaserowRuntimeFormulaArgumentType()]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0].year


class RuntimeHour(RuntimeFormulaFunction):
    type = "hour"

    args = [DateTimeBaserowRuntimeFormulaArgumentType()]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0].hour


class RuntimeMinute(RuntimeFormulaFunction):
    type = "minute"

    args = [DateTimeBaserowRuntimeFormulaArgumentType()]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0].minute


class RuntimeSecond(RuntimeFormulaFunction):
    type = "second"

    args = [DateTimeBaserowRuntimeFormulaArgumentType()]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0].second


class RuntimeNow(RuntimeFormulaFunction):
    type = "now"

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return timezone.now()


class RuntimeToday(RuntimeFormulaFunction):
    type = "today"

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return timezone.localdate()


class RuntimeGetProperty(RuntimeFormulaFunction):
    type = "get_property"

    args = [
        DictBaserowRuntimeFormulaArgumentType(),
        TextBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0].get(args[1])


class RuntimeRandomInt(RuntimeFormulaFunction):
    type = "random_int"

    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return random.randint(int(args[0]), int(args[1]))  # nosec: B311


class RuntimeRandomFloat(RuntimeFormulaFunction):
    type = "random_float"

    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return random.uniform(float(args[0]), float(args[1]))  # nosec: B311


class RuntimeRandomBool(RuntimeFormulaFunction):
    type = "random_bool"

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return random.choice([True, False])  # nosec: B311


class RuntimeGenerateUUID(RuntimeFormulaFunction):
    type = "generate_uuid"

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return str(uuid.uuid4())


class RuntimeIf(RuntimeFormulaFunction):
    type = "if"

    def validate_type_of_args(self, args) -> Optional[FormulaArg]:
        arg_type = BooleanBaserowRuntimeFormulaArgumentType()
        if not arg_type.test(args[0]):
            return args[0]

        return None

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[1] if args[0] else args[2]
