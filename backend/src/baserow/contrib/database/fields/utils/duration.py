import re
import typing
from datetime import timedelta
from typing import List, Optional, Union

from django.core.exceptions import ValidationError
from django.db.models import (
    DecimalField,
    FloatField,
    Func,
    IntegerField,
    TextField,
    Value,
)
from django.db.models.functions import Cast, Extract, Mod

from baserow.core.duration import (
    D_H,
    D_H_M,
    D_H_M_NO_COLONS,
    D_H_M_S,
    D_H_M_S_NO_COLONS,
    H_M,
    H_M_S,
    H_M_S_S,
    H_M_S_SS,
    H_M_S_SSS,
    parse_duration_value,
    postgres_interval_to_seconds,  # noqa: F401
)
from baserow.core.psycopg import is_psycopg3

if typing.TYPE_CHECKING:
    from baserow.contrib.database.fields.models import DurationField


def rround(value: float, ndigits: int = 0) -> int:
    """
    Rounds a float to the specified number of decimal places. Python round will round
    0.5 to 0, but we want it to round to 1. See
    https://docs.python.org/3/library/functions.html#round for more info.

    :param value: the value to round
    :param ndigits: the number of digits to round to
    """

    digit_value = 10**ndigits
    # note: for values below 0 we need to round down
    return int(value * digit_value + (0.5 if value >= 0 else -0.5)) / digit_value


# for `sql_interval_to_text_format` values see
# https://www.postgresql.org/docs/11/functions-formatting.html#FUNCTIONS-FORMATTING-DATETIME-TABLE

# `ms_precision` tells what microseconds precision should be used in db
# `sql_text_to_interval_format` operates on a tuple of regexes in following order:
# day
# hour
# minute
# second+mseconds
DURATION_FORMATS = {
    H_M: {
        "name": "hours:minutes",
        "round_func": lambda value: rround(value / 60) * 60,
        "sql_round_func": "(EXTRACT(EPOCH FROM p_in::INTERVAL) / 60)::int * 60",
        "format_func": lambda d, h, m, s: "%d:%02d" % (d * 24 + h, m),
        "sql_interval_to_text_format": "FMHH24:MI",
        "ms_precision": None,
        "sql_text_to_interval_format": (
            None,
            r"^(\d+):",
            r"^\d+:(\d+)",
            None,
        ),
    },
    H_M_S: {
        "name": "hours:minutes:seconds",
        "round_func": lambda value: rround(value, 0),
        "sql_round_func": "EXTRACT(EPOCH FROM p_in::INTERVAL)::int",
        "format_func": lambda d, h, m, s: "%d:%02d:%02d" % (d * 24 + h, m, s),
        "sql_interval_to_text_format": "FMHH24:MI:SS",
        "ms_precision": None,
        "sql_text_to_interval_format": (
            None,
            r"^(\d+):",
            r"^\d+:(\d+)",
            r"^\d+:\d+:(\d+\.?\d*)",
        ),
    },
    H_M_S_S: {
        "name": "hours:minutes:seconds:deciseconds",
        "round_func": lambda value: rround(value, 1),
        "sql_round_func": "ROUND(EXTRACT(EPOCH FROM p_in::INTERVAL)::NUMERIC, 1)",
        "format_func": lambda d, h, m, s: "%d:%02d:%04.1f" % (d * 24 + h, m, s),
        "sql_interval_to_text_format": "FMHH24:MI:SS.MS",
        "ms_precision": 1,
        "sql_text_to_interval_format": (
            None,
            r"^(\d+):",
            r"^\d+:(\d+)",
            r"^\d+:\d+:(\d+\.?\d*)",
        ),
    },
    H_M_S_SS: {
        "name": "hours:minutes:seconds:centiseconds",
        "round_func": lambda value: rround(value, 2),
        "sql_round_func": "ROUND(EXTRACT(EPOCH FROM p_in::INTERVAL)::NUMERIC, 2)",
        "format_func": lambda d, h, m, s: "%d:%02d:%05.2f" % (d * 24 + h, m, s),
        "sql_interval_to_text_format": "FMHH24:MI:SS.MS",
        "ms_precision": 2,
        "sql_text_to_interval_format": (
            None,
            r"^(\d+):",
            r"^\d+:(\d+)",
            r"^\d+:\d+:(\d+\.?\d*)",
        ),
    },
    H_M_S_SSS: {
        "name": "hours:minutes:seconds:milliseconds",
        "round_func": lambda value: rround(value, 3),
        "sql_round_func": "ROUND(EXTRACT(EPOCH FROM p_in::INTERVAL)::NUMERIC, 3)",
        "format_func": lambda d, h, m, s: "%d:%02d:%06.3f" % (d * 24 + h, m, s),
        "sql_interval_to_text_format": "FMHH24:MI:SS.MS",
        "ms_precision": 3,
        "sql_text_to_interval_format": (
            None,
            r"^(\d+):",
            r"^\d+:(\d+)",
            r"^\d+:\d+:(\d+\.?\d*)",
        ),
    },
    D_H: {
        "name": "days:hours",
        "round_func": lambda value: rround(value / 3600) * 3600,
        "sql_round_func": "(EXTRACT(EPOCH FROM p_in::INTERVAL) / 3600)::int * 3600",
        "format_func": lambda d, h, m, s: "%dd %dh" % (d, h),
        "sql_interval_to_text_format": 'FMDD"d" FMHH24"h"',
        "ms_precision": None,
        "sql_text_to_interval_format": (r"^(\d+)d\s*", r"^\dd\s*(\d+)h", None, None),
    },
    D_H_M: {
        "name": "days:hours:minutes",
        "round_func": lambda value: rround(value / 60) * 60,
        "sql_round_func": "(EXTRACT(EPOCH FROM p_in::INTERVAL) / 60)::int * 60",
        "format_func": lambda d, h, m, s: "%dd %d:%02d" % (d, h, m),
        "sql_interval_to_text_format": 'FMDD"d" FMHH24":"MI',
        "ms_precision": None,
        "sql_text_to_interval_format": (r"^(\d+)d", r"(\d+):", r":(\d+)", None),
    },
    D_H_M_S: {
        "name": "days:hours:minutes:seconds",
        "round_func": lambda value: rround(value, 0),
        "sql_round_func": "EXTRACT(EPOCH FROM p_in::INTERVAL)::int",
        "format_func": lambda d, h, m, s: "%dd %d:%02d:%02d" % (d, h, m, s),
        "sql_interval_to_text_format": 'FMDD"d" FMHH24":"MI":"SS',
        "ms_precision": None,
        "sql_text_to_interval_format": (
            r"^(\d+)d",
            r"\d+d\s*(\d+):",
            r"\d+d\s*\d+:(\d+)",
            r":\d+:(\d+\.?\d*)",
        ),
    },
    D_H_M_NO_COLONS: {
        "name": "days:hours:minutes:with_spaces",
        "round_func": lambda value: rround(value / 60) * 60,
        "sql_round_func": "(EXTRACT(EPOCH FROM p_in::INTERVAL) / 60)::int * 60",
        "format_func": lambda d, h, m, s: "%dd %dh %02dm" % (d, h, m),
        "sql_interval_to_text_format": 'FMDD"d" FMHH24"h" MI"m"',
        "ms_precision": None,
        "sql_text_to_interval_format": (
            r"^(\d+)d",
            r"(\d+)h",
            r"(\d+)m",
            None,
        ),
    },
    D_H_M_S_NO_COLONS: {
        "name": "days:hours:minutes:seconds:with_spaces",
        "round_func": lambda value: rround(value, 0),
        "sql_round_func": "EXTRACT(EPOCH FROM p_in::INTERVAL)::int",
        "format_func": lambda d, h, m, s: "%dd %dh %02dm %02ds" % (d, h, m, s),
        "sql_interval_to_text_format": 'FMDD"d" FMHH24"h" MI"m" SS"s"',
        "ms_precision": 0,
        "sql_text_to_interval_format": (
            r"^(\d+)d",
            r"(\d+)h",
            r"(\d+)m",
            r"(\d+\.?\d*)s",
        ),
    },
}


def hours_with_days_search_expr(field_name):
    return Mod(
        Cast(Extract(field_name, "hour"), output_field=IntegerField()), Value(24)
    )


# The tokens used in the format strings and their utility functions. NOTE: the order of
# duration units is crucial, as it ranges from the largest to the smallest unit. This
# order is significant because it helps determine the precision of different duration
# formats (see is_duration_format_conversion_lossy down below), which are created by
# combining various tokens. If there's a need to convert between these formats, it might
# be necessary to backup data beforehand to prevent loss of precision.
DURATION_FORMAT_TOKENS = {
    "d": {
        "search_expr": {
            "default": lambda field_name: Func(
                Cast(
                    Func(
                        Extract(field_name, "epoch", output_field=IntegerField())
                        / Value(86400),
                        function="TRUNC",
                        output_field=IntegerField(),
                    ),
                    output_field=TextField(),
                ),
                Value("d"),
                function="CONCAT",
            ),
        },
    },
    "h": {
        "search_expr": {
            D_H: lambda field_name: Func(
                hours_with_days_search_expr(field_name), Value("h"), function="CONCAT"
            ),
            D_H_M: hours_with_days_search_expr,
            D_H_M_S: hours_with_days_search_expr,
            D_H_M_NO_COLONS: hours_with_days_search_expr,
            D_H_M_S_NO_COLONS: hours_with_days_search_expr,
            "default": lambda field_name: Cast(
                Func(
                    Extract(field_name, "epoch", output_field=IntegerField())
                    / Value(3600),
                    function="TRUNC",
                    output_field=IntegerField(),
                ),
                output_field=TextField(),
            ),
        },
    },
    "mm": {
        "search_expr": {
            "default": lambda field_name: Func(
                Extract(field_name, "minutes", output_field=IntegerField()),
                Value("FM00"),
                function="TO_CHAR",
                output_field=TextField(),
            ),
        },
    },
    "ss": {
        "search_expr": {
            "default": lambda field_name: Func(
                Cast(
                    Extract(field_name, "seconds", output_field=FloatField()),
                    output_field=DecimalField(max_digits=15, decimal_places=0),
                ),
                Value("FM00"),
                function="TO_CHAR",
                output_field=TextField(),
            ),
        },
    },
    "ss.s": {
        "search_expr": {
            "default": lambda field_name: Func(
                Cast(
                    Extract(field_name, "seconds", output_field=DecimalField()),
                    output_field=DecimalField(max_digits=15, decimal_places=1),
                ),
                Value("FM00.0"),
                function="TO_CHAR",
                output_field=TextField(),
            )
        },
    },
    "ss.ss": {
        "search_expr": {
            "default": lambda field_name: Func(
                Cast(
                    Extract(field_name, "seconds", output_field=DecimalField()),
                    output_field=DecimalField(max_digits=15, decimal_places=2),
                ),
                Value("FM00.00"),
                function="TO_CHAR",
                output_field=TextField(),
            )
        },
    },
    "ss.sss": {
        "search_expr": {
            "default": lambda field_name: Func(
                Cast(
                    Extract(field_name, "seconds", output_field=DecimalField()),
                    output_field=DecimalField(max_digits=15, decimal_places=3),
                ),
                Value("FM00.000"),
                function="TO_CHAR",
                output_field=TextField(),
            )
        },
    },
}


def duration_value_to_timedelta(
    value: Union[int, float, timedelta, str, None], format: str
) -> Optional[timedelta]:
    """
    Converts a raw value for a duration field to a timedelta object. It treats
    the value as a number of seconds if it is an integer or float. If it is a
    string it will parse it using the provided format. Even if the format doesn't
    match exactly, it will still try to parse it as best as possible.

    :param value: The raw value to convert.
    :param format: The format to use when parsing the value if it is a string
        and to round the value to.
    :return: The timedelta object.
    :raises ValueError: If the value has an invalid type.
    :raise OverflowError: If the value is too big to be converted to a timedelta.
    """

    if format not in DURATION_FORMATS:
        raise ValueError(f"{format} is not a valid duration format.")

    if value is None:
        return None
    elif isinstance(value, timedelta):
        return value

    # Since our view_filters are storing the number of seconds as string, let's try
    # to convert it to a number first. Please note that this is different in the
    # frontend where the input value is parsed accordingly to the field format.
    try:
        value = float(value)
    except ValueError:
        pass

    # any value is valid if this is a number
    if isinstance(value, (int, float)):
        total_seconds = value
    elif isinstance(value, str):
        total_seconds = parse_duration_value(value, format)
    else:
        raise ValueError(
            "The provided value should be a valid integer or string according to the "
            f"{format} format.",
        )

    round_func = DURATION_FORMATS[format]["round_func"]
    return timedelta(seconds=round_func(total_seconds))


def prepare_duration_value_for_db(
    value, duration_format, default_exc=ValidationError
) -> Optional[timedelta]:
    """
    Prepares a value for a duration field to be stored in the database. It
    converts the value to a timedelta object if it is a valid integer or string
    according to the format. If something is wrong with the value, a
    default_exc is raised with the correct error code and message.

    :param value: The raw value to convert.
    :param duration_format: The format to use when parsing the value if it is a
        string and to round the value to.
    :param default_exc: The exception to raise if something is wrong with the
        value.
    :return: The timedelta object.
    """

    try:
        return duration_value_to_timedelta(value, duration_format)
    except ValueError:
        raise default_exc(
            f"The value {value} is not a valid duration.",
            code="invalid",
        )
    except OverflowError:
        raise default_exc(
            f"Value {value} is too large. The maximum is {timedelta.max}.",
            code="invalid",
        )


def format_duration_value(
    duration: Optional[timedelta], duration_format
) -> Optional[str]:
    """
    Format a duration value according to the provided format.

    :param duration: The duration to format.
    :param duration_format: The format to use.
    :return: The formatted duration.
    """

    if duration is None:
        return None
    sign = ""
    if duration < timedelta(0):
        duration = -1 * duration
        sign = "-"
    days = duration.days
    hours = duration.seconds // 3600
    mins = duration.seconds % 3600 // 60
    secs = duration.seconds % 60 + duration.microseconds / 10**6

    format_func = DURATION_FORMATS[duration_format]["format_func"]
    return f"{sign}{format_func(days, hours, mins, secs)}"


def tokenize_formatted_duration(duration_format: str) -> List[str]:
    """
    Tokenize a formatted duration format returning a list of tokens.

    :param formatted_value: The formatted duration string.
    :return: A list with tokens.
    """

    return re.split("[: ]", duration_format)


def is_duration_format_conversion_lossy(new_format, old_format):
    """
    Returns True if converting from starting_format to ending_format will result in a
    loss of precision.

    :param starting_format: The format to convert from.
    :param ending_format: The format to convert to.
    """

    ordered_tokens = list(DURATION_FORMAT_TOKENS.keys())

    new_lst = tokenize_formatted_duration(new_format)[-1]
    old_lst = tokenize_formatted_duration(old_format)[-1]

    return ordered_tokens.index(old_lst) > ordered_tokens.index(new_lst)


def get_duration_search_expression(field: "DurationField") -> Func:
    """
    Returns a search expression that can be used to search the field as a formatted
    string.

    :param field: The field to get the search expression for.
    :return: A search expression that can be used to search the field as a formatted
        string.
    """

    search_exprs = []
    for token in tokenize_formatted_duration(field.duration_format):
        search_exp_functions = DURATION_FORMAT_TOKENS[token]["search_expr"]
        search_expr_func = search_exp_functions.get(
            field.duration_format, search_exp_functions["default"]
        )
        search_exprs.append(search_expr_func(field.db_column))
    separators = [Value(" ")] * len(search_exprs)
    # interleave a separator between each extract_expr
    exprs = [expr for pair in zip(search_exprs, separators) for expr in pair][:-1]
    return Func(*exprs, function="CONCAT")


def duration_value_sql_to_text(field: "DurationField") -> str:
    """
    Returns a SQL expression that can be used to convert the duration value to a
    formatted string.

    :param field: The field to get the SQL expression for.
    :return: A string containing the SQL expression that can be used to convert the
        duration value to a formatted string.
    """

    field_format = field.duration_format
    conversion_format = DURATION_FORMATS[field_format]["sql_interval_to_text_format"]
    ms_precision = DURATION_FORMATS[field_format]["ms_precision"]
    format_func = f"br_interval_to_text(p_in::interval, '{conversion_format}'::text, {ms_precision or 'NULL'})"
    return format_func


def text_value_sql_to_duration(field: "DurationField") -> str:
    """
    Returns a SQL expression that can be used to convert a text value to duration value.

    Note: text value should conform duration format's patterns to be properly extracted.

    :param field: target DurationField
    :return: SQL expression string
    """

    db_function_args = DURATION_FORMATS[field.duration_format][
        "sql_text_to_interval_format"
    ]
    args = [f"'{arg or 'NULL'}'" for arg in db_function_args]
    return f"br_text_to_interval(p_in, {','.join(args)});"


if is_psycopg3:
    from psycopg.types.datetime import IntervalLoader

    from baserow.core.psycopg import psycopg

    class BaserowIntervalLoader(IntervalLoader):
        """
        We're not doing anything special here, but if we don't register this
        adapter tests will fail when parsing negative intervals.
        """

        def load(self, data):
            return super().load(data)

    psycopg.adapters.register_loader("interval", BaserowIntervalLoader)
