from zoneinfo import ZoneInfo

from baserow.core.formula.argument_types import (
    DateTimeBaserowRuntimeFormulaArgumentType,
    NumberBaserowRuntimeFormulaArgumentType,
    TextBaserowRuntimeFormulaArgumentType,
)
from baserow.core.formula.registries import RuntimeFormulaFunction
from baserow.core.formula.types import FormulaArgs, FormulaContext
from baserow.core.formula.validator import ensure_string


class RuntimeConcat(RuntimeFormulaFunction):
    type = "concat"

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return "".join([ensure_string(a) for a in args])

    def validate_number_of_args(self, args):
        return len(args) >= 2


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
