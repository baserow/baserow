import json
import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from baserow.core.duration import (
    format_value_with_duration_format,
    parse_value_with_duration_format,
)
from baserow.core.exceptions import InstanceTypeDoesNotExist
from baserow.core.formula import BaserowFormulaSyntaxError
from baserow.core.formula.argument_types import (
    AnyBaserowRuntimeFormulaArgumentType,
    ArrayOfNumbersBaserowRuntimeFormulaArgumentType,
    BooleanBaserowRuntimeFormulaArgumentType,
    DateTimeBaserowRuntimeFormulaArgumentType,
    DatetimeFormatBaserowRuntimeFormulaArgumentType,
    DecimalSeparatorBaserowRuntimeFormulaArgumentType,
    DictBaserowRuntimeFormulaArgumentType,
    DurationBaserowRuntimeFormulaArgumentType,
    DurationFormatBaserowRuntimeFormulaArgumentType,
    NumberBaserowRuntimeFormulaArgumentType,
    TextBaserowRuntimeFormulaArgumentType,
    ThousandSeparatorBaserowRuntimeFormulaArgumentType,
    TimedeltaBaserowRuntimeFormulaArgumentType,
    TimezoneBaserowRuntimeFormulaArgumentType,
)
from baserow.core.formula.registries import RuntimeFormulaFunction
from baserow.core.formula.types import FormulaArg, FormulaArgs, FormulaContext
from baserow.core.formula.utils.date import convert_date_format_moment_to_python
from baserow.core.formula.validator import (
    BaserowFormulaJSONEncoder,
    ensure_array,
    ensure_datetime,
    ensure_string,
)
from baserow.core.utils import to_path


class RuntimeConcat(RuntimeFormulaFunction):
    type = "concat"
    min_args = 2

    def validate_type_of_args(self, args) -> list[tuple[int, FormulaArg]]:
        arg_type = TextBaserowRuntimeFormulaArgumentType()
        return [
            (index, arg) for index, arg in enumerate(args) if not arg_type.test(arg)
        ]

    def validate_number_of_args(self, args):
        return len(args) >= self.min_args

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return "".join([ensure_string(a) for a in args])


class RuntimeGet(RuntimeFormulaFunction):
    type = "get"
    args = [TextBaserowRuntimeFormulaArgumentType()]

    def validate_args(
        self,
        args: FormulaArgs,
        validation_context: Optional[Dict[str, Any]] = None,
    ):
        super().validate_args(args)

        provider_name, *rest = to_path(args[0])
        if not provider_name:
            raise BaserowFormulaSyntaxError(
                f"The '{self.type}' function arguments "
                "must start with a formula provider name."
            )

        data_provider_type_registry = validation_context["data_provider_type_registry"]
        try:
            provider = data_provider_type_registry.get(provider_name)
        except InstanceTypeDoesNotExist:
            # Re-raise the exception but with a more precise message. We
            # are at a stage where we have enough variables that we can
            # precisely say where the argument is wrong.
            raise InstanceTypeDoesNotExist(
                provider_name,
                f"The formula provider '{provider_name}' "
                f"used in '{args[0]}' does not exist in this module.",
            )
        provider.is_valid(rest)

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return context[args[0]]


class RuntimeAdd(RuntimeFormulaFunction):
    type = "add"

    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def validate_type_of_args(self, args) -> list[tuple[int, FormulaArg]]:
        if len(args) == 2:
            a, b = args
            num = NumberBaserowRuntimeFormulaArgumentType()
            dt = DateTimeBaserowRuntimeFormulaArgumentType()
            td = TimedeltaBaserowRuntimeFormulaArgumentType()

            if num.test(a) and num.test(b):
                return []
            if td.test(a) and td.test(b):
                return []
            if (td.test(a) and num.test(b)) or (num.test(a) and td.test(b)):
                return []
            if (dt.test(a) and td.test(b)) or (td.test(a) and dt.test(b)):
                return []
            if not (num.test(a) or dt.test(a) or td.test(a)):
                return [(0, a)]
            if not (num.test(b) or dt.test(b) or td.test(b)):
                return [(1, b)]

            # Reject invalid pairs, e.g.: datetime + number, datetime + datetime, etc.
            return [(0, a)]

        return super().validate_type_of_args(args)

    def parse_args(self, args: FormulaArgs) -> FormulaArgs:
        if any(isinstance(a, (datetime, timedelta)) for a in args):
            return list(args)
        return super().parse_args(args)

    def execute(self, context: FormulaContext, args: FormulaArgs):
        a, b = args

        if isinstance(a, timedelta) and not isinstance(b, (datetime, timedelta)):
            b = timedelta(seconds=b)
        elif isinstance(b, timedelta) and not isinstance(a, (datetime, timedelta)):
            a = timedelta(seconds=a)

        return a + b


class RuntimeMinus(RuntimeFormulaFunction):
    type = "minus"

    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def validate_type_of_args(self, args) -> list[tuple[int, FormulaArg]]:
        if len(args) == 2:
            a, b = args
            num = NumberBaserowRuntimeFormulaArgumentType()
            dt = DateTimeBaserowRuntimeFormulaArgumentType()
            td = TimedeltaBaserowRuntimeFormulaArgumentType()

            if num.test(a) and num.test(b):
                return []
            if td.test(a) and td.test(b):
                return []
            if (td.test(a) and num.test(b)) or (num.test(a) and td.test(b)):
                return []
            if dt.test(a) and td.test(b):
                return []
            if not (num.test(a) or dt.test(a) or td.test(a)):
                return [(0, a)]

            # Reject invalid pairs, e.g.: datetime - number, etc.
            return [(1, b)]

        return super().validate_type_of_args(args)

    def parse_args(self, args: FormulaArgs) -> FormulaArgs:
        if any(isinstance(a, (datetime, timedelta)) for a in args):
            return list(args)
        return super().parse_args(args)

    def execute(self, context: FormulaContext, args: FormulaArgs):
        a, b = args

        if isinstance(a, timedelta) and not isinstance(b, (datetime, timedelta)):
            b = timedelta(seconds=b)
        elif isinstance(b, timedelta) and not isinstance(a, (datetime, timedelta)):
            a = timedelta(seconds=a)

        return a - b


class RuntimeMultiply(RuntimeFormulaFunction):
    type = "multiply"

    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def validate_type_of_args(self, args) -> list[tuple[int, FormulaArg]]:
        if len(args) == 2:
            a, b = args
            num = NumberBaserowRuntimeFormulaArgumentType()
            td = TimedeltaBaserowRuntimeFormulaArgumentType()

            if num.test(a) and num.test(b):
                return []
            if (td.test(a) and num.test(b)) or (num.test(a) and td.test(b)):
                return []
            if not (num.test(a) or td.test(a)):
                return [(0, a)]

            # Reject invalid pairs, e.g.: datetime * number, etc.
            return [(1, b)]

        return super().validate_type_of_args(args)

    def parse_args(self, args: FormulaArgs) -> FormulaArgs:
        if any(isinstance(a, timedelta) for a in args):
            return list(args)
        return super().parse_args(args)

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return args[0] * args[1]


class RuntimeDivide(RuntimeFormulaFunction):
    type = "divide"

    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(),
    ]

    def validate_type_of_args(self, args) -> list[tuple[int, FormulaArg]]:
        if len(args) == 2:
            a, b = args
            num = NumberBaserowRuntimeFormulaArgumentType()
            td = TimedeltaBaserowRuntimeFormulaArgumentType()

            if num.test(a) and num.test(b):
                return []
            if td.test(a) and num.test(b):
                return []
            if not (num.test(a) or td.test(a)):
                return [(0, a)]

            # Reject invalid pairs, e.g.: datetime / number, etc.
            return [(1, b)]

        return super().validate_type_of_args(args)

    def parse_args(self, args: FormulaArgs) -> FormulaArgs:
        if any(isinstance(a, timedelta) for a in args):
            return list(args)
        return super().parse_args(args)

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


class RuntimeAbs(RuntimeFormulaFunction):
    type = "abs"

    args = [NumberBaserowRuntimeFormulaArgumentType()]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return abs(args[0])


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
        DatetimeFormatBaserowRuntimeFormulaArgumentType(),
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


class RuntimeRange(RuntimeFormulaFunction):
    type = "range"

    args = [
        NumberBaserowRuntimeFormulaArgumentType(cast_to_int=True),
        NumberBaserowRuntimeFormulaArgumentType(optional=True, cast_to_int=True),
        NumberBaserowRuntimeFormulaArgumentType(optional=True, cast_to_int=True),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        if len(args) == 1:
            start, stop, step = 0, args[0], 1
        elif len(args) == 2:
            start, stop, step = args[0], args[1], 1
        else:
            start, stop, step = args[0], args[1], args[2]

        if step == 0:
            raise BaserowFormulaSyntaxError(
                "The 'range' function step argument must not be zero."
            )

        # range() computes its length lazily, so this is cheap
        result = range(start, stop, step)
        max_items = settings.FORMULA_RANGE_MAX_ITEMS
        if len(result) > max_items:
            raise BaserowFormulaSyntaxError(
                f"The 'range' function cannot generate more than {max_items} items."
            )

        return list(result)


class RuntimeToJson(RuntimeFormulaFunction):
    type = "to_json"

    args = [AnyBaserowRuntimeFormulaArgumentType()]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        # Compact separators are used to match the frontend's `JSON.stringify` output.
        return json.dumps(
            args[0],
            cls=BaserowFormulaJSONEncoder,
            allow_nan=False,
            separators=(",", ":"),
        )


class RuntimeFromJson(RuntimeFormulaFunction):
    type = "from_json"

    args = [TextBaserowRuntimeFormulaArgumentType()]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        # Parse a JSON-encoded string back into a value. Returns `None` when the
        # input isn't valid JSON.
        try:
            return json.loads(args[0])
        except (TypeError, ValueError):
            return None


class RuntimeNull(RuntimeFormulaFunction):
    type = "null"

    args = []

    def execute(self, context: FormulaContext, args: FormulaArgs):
        return None


class RuntimeNumberFormat(RuntimeFormulaFunction):
    type = "number_format"

    args = [
        NumberBaserowRuntimeFormulaArgumentType(),
        NumberBaserowRuntimeFormulaArgumentType(optional=True, cast_to_int=True),
        ThousandSeparatorBaserowRuntimeFormulaArgumentType(optional=True),
        DecimalSeparatorBaserowRuntimeFormulaArgumentType(optional=True),
    ]

    def validate_args(self, args, validation_context=None):
        super().validate_args(args, validation_context)
        if len(args) >= 4 and args[2] == args[3]:
            raise BaserowFormulaSyntaxError(
                "The thousand separator and decimal separator cannot be the same."
            )

    def execute(self, context: FormulaContext, args: FormulaArgs):
        value = args[0]
        decimal_places = max(int(args[1]), 0) if len(args) > 1 else 0
        thousand_sep = args[2] if len(args) > 2 else ","
        decimal_sep = args[3] if len(args) > 3 else "."

        is_negative = value < 0
        abs_value = abs(value)
        formatted = f"{abs_value:,.{decimal_places}f}"

        if decimal_places > 0:
            int_part, dec_part = formatted.split(".")
        else:
            int_part = formatted
            dec_part = None

        int_part = int_part.replace(",", thousand_sep)
        result = int_part if dec_part is None else int_part + decimal_sep + dec_part

        if is_negative:
            result = "-" + result

        return result


class RuntimeToDuration(RuntimeFormulaFunction):
    type = "to_duration"

    args = [
        DurationBaserowRuntimeFormulaArgumentType(),
        DurationFormatBaserowRuntimeFormulaArgumentType(optional=True),
    ]

    def _format_error(self, value, duration_format):
        return f"'{value}' could not be parsed using format '{duration_format}'."

    def validate_type_of_args(self, args) -> list[tuple[int, FormulaArg]]:
        # When a format is provided, arg 0's validity depends on the format.
        # Defer checking arg 0 to validate_args() in that case.
        if len(args) == 2:
            if not self.args[1].test(args[1]):
                return [(1, args[1])]
            return []

        return super().validate_type_of_args(args)

    def validate_args(self, args, validation_context=None):
        super().validate_args(args, validation_context)

        if len(args) != 2:
            return

        value, duration_format = args
        if isinstance(value, str):
            if parse_value_with_duration_format(value, duration_format) is None:
                raise BaserowFormulaSyntaxError(
                    self._format_error(value, duration_format)
                )

    def parse_args(self, args: FormulaArgs) -> FormulaArgs:
        # When the format arg is provided, defer parsing of the 1st arg to
        # execute() so the raw value arg is checked later in combination
        # with the format arg.
        if len(args) == 2:
            return [args[0], self.args[1].parse(args[1])]

        return super().parse_args(args)

    def execute(self, context: FormulaContext, args: FormulaArgs):
        if len(args) == 2:
            value, duration_format = args
            # Arg 0 may resolve to a timedelta at runtime (e.g. from a
            # get() on a duration field), in which case it doesn't make sense
            # to apply the format.
            if isinstance(value, timedelta):
                raise BaserowFormulaSyntaxError(
                    "A duration format cannot be applied to a timedelta value."
                )

            result = parse_value_with_duration_format(value, duration_format)
            if result is None:
                raise BaserowFormulaSyntaxError(
                    self._format_error(value, duration_format)
                )
            return result

        return args[0]


class RuntimeDurationFormat(RuntimeFormulaFunction):
    type = "duration_format"

    args = [
        DurationBaserowRuntimeFormulaArgumentType(),
        DurationFormatBaserowRuntimeFormulaArgumentType(),
    ]

    def execute(self, context: FormulaContext, args: FormulaArgs):
        duration, duration_format = args
        if duration is None:
            return None
        return format_value_with_duration_format(duration, duration_format)


class RuntimeToDatetime(RuntimeFormulaFunction):
    type = "to_datetime"

    args = [
        TextBaserowRuntimeFormulaArgumentType(),
        DatetimeFormatBaserowRuntimeFormulaArgumentType(optional=True),
    ]

    def validate_args(self, args, validation_context=None):
        super().validate_args(args, validation_context)
        value = args[0]
        if len(args) == 2:
            moment_format = args[1]
            python_format = convert_date_format_moment_to_python(moment_format)
            try:
                ensure_datetime(value, date_format=python_format, strict=True)
            except ValidationError:
                raise BaserowFormulaSyntaxError(
                    f"'{value}' could not be parsed using format '{moment_format}'."
                )
        else:
            try:
                ensure_datetime(value)
            except ValidationError:
                raise BaserowFormulaSyntaxError(
                    f"'{value}' is not a valid ISO datetime string. "
                    f"Expected a format like '2024-01-15' or '2024-01-15T12:00:00'."
                )

    def execute(self, context: FormulaContext, args: FormulaArgs):
        value = args[0]
        if len(args) == 2:
            python_format = convert_date_format_moment_to_python(args[1])
            return ensure_datetime(value, date_format=python_format, strict=True)
        else:
            return ensure_datetime(value)
