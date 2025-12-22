import random
import uuid
from typing import Optional
from zoneinfo import ZoneInfo

from django.utils import timezone

from baserow.core.formula.argument_types import (
    AnyBaserowRuntimeFormulaArgumentType,
    ArrayOfNumbersBaserowRuntimeFormulaArgumentType,
    BooleanBaserowRuntimeFormulaArgumentType,
    DateTimeBaserowRuntimeFormulaArgumentType,
    DictBaserowRuntimeFormulaArgumentType,
    NumberBaserowRuntimeFormulaArgumentType,
    TextBaserowRuntimeFormulaArgumentType,
    TimezoneBaserowRuntimeFormulaArgumentType,
)
from baserow.core.formula.registries import RuntimeFormulaFunction
from baserow.core.formula.types import FormulaArg, FormulaArgs, FormulaContext
from baserow.core.formula.utils.date import convert_date_format_moment_to_python
from baserow.core.formula.validator import ensure_array, ensure_string


class RuntimeConcat(RuntimeFormulaFunction):
    type = "concat"

    def validate_type_of_args(self, args) -> Optional[FormulaArg]:
        arg_type = TextBaserowRuntimeFormulaArgumentType()
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

    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] + args[1]


class RuntimeMinus(RuntimeFormulaFunction):
    type = "minus"

    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] - args[1]


class RuntimeMultiply(RuntimeFormulaFunction):
    type = "multiply"

    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] * args[1]


class RuntimeDivide(RuntimeFormulaFunction):
    type = "divide"

    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] / args[1]


class RuntimeEqual(RuntimeFormulaFunction):
    type = "equal"
    args = [
        AnyBaserowRuntimeFormulaArgumentType(),
        AnyBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] == args[1]


class RuntimeNotEqual(RuntimeFormulaFunction):
    type = "not_equal"
    args = [
        AnyBaserowRuntimeFormulaArgumentType(),
        AnyBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] != args[1]


class RuntimeGreaterThan(RuntimeFormulaFunction):
    type = "greater_than"
    args = [
        AnyBaserowRuntimeFormulaArgumentType(),
        AnyBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] > args[1]


class RuntimeLessThan(RuntimeFormulaFunction):
    type = "less_than"
    args = [
        AnyBaserowRuntimeFormulaArgumentType(),
        AnyBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] < args[1]


class RuntimeGreaterThanOrEqual(RuntimeFormulaFunction):
    type = "greater_than_or_equal"
    args = [
        AnyBaserowRuntimeFormulaArgumentType(),
        AnyBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] >= args[1]


class RuntimeLessThanOrEqual(RuntimeFormulaFunction):
    type = "less_than_or_equal"
    args = [
        AnyBaserowRuntimeFormulaArgumentType(),
        AnyBaserowRuntimeFormulaArgumentType(),
    ]

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
        NumberBaserowRuntimeFormulaArgumentType(optional=True, cast_to_int=True),
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
        TimezoneBaserowRuntimeFormulaArgumentType(optional=True),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        datetime_obj = args[0]
        moment_format = args[1]

        if len(args) == 2:
            timezone_name = context.get_timezone_name()
        else:
            timezone_name = args[2]

        python_format = convert_date_format_moment_to_python(moment_format)
        result = datetime_obj.astimezone(ZoneInfo(timezone_name)).strftime(
            python_format
        )

        if "SSS" in moment_format:
            # When Moment's SSS is milliseconds (3 digits), but Python's %f
            # is microseconds (6 digits). We need to replace the microseconds
            # with milliseconds.
            microseconds_str = f"{datetime_obj.microsecond:06d}"
            milliseconds_str = f"{datetime_obj.microsecond // 1000:03d}"
            result = result.replace(microseconds_str, milliseconds_str)

        return result


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

    args = []

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return timezone.now()


class RuntimeToday(RuntimeFormulaFunction):
    type = "today"

    args = []

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
        NumberBaserowRuntimeFormulaArgumentType(cast_to_int=True),
        NumberBaserowRuntimeFormulaArgumentType(cast_to_int=True),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return random.randint(args[0], args[1])  # nosec: B311


class RuntimeRandomFloat(RuntimeFormulaFunction):
    type = "random_float"

    args = [
        NumberBaserowRuntimeFormulaArgumentType(cast_to_float=True),
        NumberBaserowRuntimeFormulaArgumentType(cast_to_float=True),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return random.uniform(args[0], args[1])  # nosec: B311


class RuntimeRandomBool(RuntimeFormulaFunction):
    type = "random_bool"

    args = []

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return random.choice([True, False])  # nosec: B311


class RuntimeGenerateUUID(RuntimeFormulaFunction):
    type = "generate_uuid"

    args = []

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return str(uuid.uuid4())


class RuntimeIf(RuntimeFormulaFunction):
    type = "if"

    args = [
        BooleanBaserowRuntimeFormulaArgumentType(),
        AnyBaserowRuntimeFormulaArgumentType(),
        AnyBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[1] if args[0] else args[2]


class RuntimeAnd(RuntimeFormulaFunction):
    type = "and"

    args = [
        BooleanBaserowRuntimeFormulaArgumentType(),
        BooleanBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] and args[1]


class RuntimeOr(RuntimeFormulaFunction):
    type = "or"

    args = [
        BooleanBaserowRuntimeFormulaArgumentType(),
        BooleanBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] or args[1]


class RuntimeReplace(RuntimeFormulaFunction):
    type = "replace"

    args = [
        TextBaserowRuntimeFormulaArgumentType(),
        TextBaserowRuntimeFormulaArgumentType(),
        TextBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0].replace(args[1], args[2])


class RuntimeLength(RuntimeFormulaFunction):
    type = "length"

    args = [
        AnyBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return len(args[0])


class RuntimeContains(RuntimeFormulaFunction):
    type = "contains"

    args = [
        AnyBaserowRuntimeFormulaArgumentType(),
        AnyBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[1] in args[0]


class RuntimeReverse(RuntimeFormulaFunction):
    type = "reverse"

    args = [
        AnyBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        value = args[0]

        if isinstance(value, list):
            return list(reversed(value))

        if isinstance(value, str):
            return "".join(list(reversed(value)))

        raise TypeError(f"Cannot reverse {value}")


class RuntimeJoin(RuntimeFormulaFunction):
    type = "join"

    args = [
        AnyBaserowRuntimeFormulaArgumentType(),
        TextBaserowRuntimeFormulaArgumentType(optional=True),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        value = args[0]
        separator = args[1] if len(args) == 2 else ","
        return separator.join(value)


class RuntimeSplit(RuntimeFormulaFunction):
    type = "split"

    args = [
        TextBaserowRuntimeFormulaArgumentType(),
        TextBaserowRuntimeFormulaArgumentType(optional=True),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        separator = args[1] if len(args) == 2 else None
        return args[0].split(separator)


class RuntimeIsEmpty(RuntimeFormulaFunction):
    type = "is_empty"

    args = [
        AnyBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        value = args[0]

        if value is None:
            return True

        if isinstance(value, (list, str, dict)):
            if isinstance(value, str):
                value = value.strip()
            return len(value) == 0

        return False


class RuntimeStrip(RuntimeFormulaFunction):
    type = "strip"

    args = [
        TextBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0].strip()


class RuntimeSum(RuntimeFormulaFunction):
    type = "sum"

    args = [
        ArrayOfNumbersBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return sum(args[0])


class RuntimeAvg(RuntimeFormulaFunction):
    type = "avg"

    args = [
        ArrayOfNumbersBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return sum(args[0]) / len(args[0])


class RuntimeAt(RuntimeFormulaFunction):
    type = "at"

    args = [
        AnyBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(cast_to_int=True),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        value = args[0]
        index = args[1]
        return value[index]


class RuntimeToArray(RuntimeFormulaFunction):
    type = "to_array"

    args = [TextBaserowRuntimeFormulaArgumentType()]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return ensure_array(args[0])
