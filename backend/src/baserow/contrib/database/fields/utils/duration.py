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

from baserow.core.psycopg import is_psycopg3

H_M = "h:mm"
H_M_S = "h:mm:ss"
H_M_S_S = "h:mm:ss.s"
H_M_S_SS = "h:mm:ss.ss"
H_M_S_SSS = "h:mm:ss.sss"
D_H = "d h"
D_H_M = "d h:mm"  # 1d 11:11
D_H_M_S = "d h:mm:ss"
D_H_M_NO_COLONS = "d h mm"  # 1d 2h 3m, 1d 3m
D_H_M_S_NO_COLONS = "d h mm ss"  # 1d2h3m4s, 1h 2m

MOST_ACCURATE_DURATION_FORMAT = H_M_S_SSS


if typing.TYPE_CHECKING:
    from baserow.contrib.database.fields.models import DurationField


def total_secs(
    days: Optional[int] = None,
    hours: Optional[int] = None,
    mins: Optional[int] = None,
    secs: Optional[Union[int, float]] = None,
) -> float:
    """
    Calculate number of seconds from higher-order units.

    :param days: number of days
    :param hours: number of hours
    :param mins: number of minutes
    :param secs: number of seconds (with milliseconds if provided as a float)

    :return: number of seconds
    """

    return (
        int(days or 0) * 86400
        + int(hours or 0) * 3600
        + int(mins or 0) * 60
        + float(secs or 0.0)
    )


POSTGRES_INTERVAL_FORMAT = re.compile(
    r"""
    (?P<years>-?\d+)\s+years?\s*|
    (?P<months>-?\d+)\s+mons?\s*|
    (?P<days>-?\d+)\s+days?\s*|
    (?P<time>(-?\d{1,2}):(\d{2}):(\d{2}))?
""",
    re.VERBOSE,
)


def postgres_interval_to_seconds(interval_str: str) -> Optional[float]:
    matches = POSTGRES_INTERVAL_FORMAT.finditer(interval_str)

    params = {
        "days": 0,
        "seconds": 0,
        "microseconds": 0,
        "milliseconds": 0,
        "minutes": 0,
        "hours": 0,
        "weeks": 0,
    }

    valid = False
    for match in matches:
        if match.group("years"):
            params["days"] += int(match.group("years")) * 365
            valid = True
        if match.group("months"):
            params["days"] += int(match.group("months")) * 30
            valid = True
        if match.group("days"):
            params["days"] += int(match.group("days"))
            valid = True
        if match.group("time"):
            time_parts = match.group("time").split(":")
            params["hours"] += int(time_parts[0])
            params["minutes"] += int(time_parts[1])
            params["seconds"] += int(time_parts[2])
            valid = True

    return timedelta(**params).total_seconds() if valid else None


# These regexps are supposed to tokenize the provided duration value and to return a
# proper number of seconds based on format and the tokens. NOTE: Keep these in sync with
# web-frontend/modules/database/utils/duration.js:DURATION_REGEXPS
DURATION_REGEXPS = {
    # 1d 10h 20m 30s
    # 1d 30m 40.50s
    # 1d 30s
    re.compile(  # optionally capture `1d`
        r"^((?P<days>\d+)(?:d\s*))?"
        # optionally capture 1h
        r"((?P<hours>\d+)(?:h\s*))?"
        # optionally capture 1m
        r"((?P<mins>\d+)(?:m\s*|\s+))?"
        # optionally capture 1.2s
        r"((?P<secs>\d+|\d+.\d+)?(?:s\s*))?$"
    ): {
        "default": lambda days, hours, mins, secs: total_secs(
            days=days, hours=hours, mins=mins, secs=secs
        ),
    },
    # 1d 11:12:13.14
    # 1 11:12:13.14
    re.compile(r"^(\d+)(?:d\s*|\s+)(\d+):(\d+):(\d+|\d+.\d+)$"): {
        "default": lambda d, h, m, s: total_secs(days=d, hours=h, mins=m, secs=s),
    },
    # 11:12:13.14
    re.compile(r"^(\d+):(\d+):(\d+|\d+.\d+)$"): {
        "default": lambda h, m, s: total_secs(hours=h, mins=m, secs=s),
    },
    # 1d 12h
    # 1 12h
    re.compile(r"^(\d+)(?:d\s*|\s+)(\d+)h$"): {
        "default": lambda d, h: total_secs(days=d, hours=h),
    },
    # 1234h
    re.compile(r"^(\d+)h$"): {
        "default": lambda h: total_secs(hours=h),
    },
    # 123d
    re.compile(r"^(\d+)d$"): {
        "default": lambda d: total_secs(days=d),
    },
    # 1d 11:12
    # 1 11:12
    re.compile(r"^(\d+)(?:d\s*|\s+)(\d+):(\d+)$"): {
        H_M: lambda d, h, m: total_secs(days=d, hours=h, mins=m),
        D_H: lambda d, h, m: total_secs(days=d, hours=h, mins=m),
        D_H_M: lambda d, h, m: total_secs(days=d, hours=h, mins=m),
        D_H_M_NO_COLONS: lambda d, h, m: total_secs(days=d, hours=h, mins=m),
        "default": lambda d, m, s: total_secs(days=d, mins=m, secs=s),
    },
    # 1d 11:12.23
    # 1 11:12.23
    re.compile(r"^(\d+)(?:d\s*|\s+)(\d+):(\d+.\d+)$"): {
        "default": lambda d, m, s: total_secs(days=d, mins=m, secs=s),
    },
    # 11:12
    re.compile(r"^(\d+):(\d+)$"): {
        H_M: lambda h, m: total_secs(hours=h, mins=m),
        D_H: lambda h, m: total_secs(hours=h, mins=m),
        D_H_M: lambda h, m: total_secs(hours=h, mins=m),
        "default": lambda m, s: total_secs(mins=m, secs=s),
    },
    # 11:12.134
    re.compile(r"^(\d+):(\d+.\d+)$"): {
        "default": lambda m, s: total_secs(mins=m, secs=s),
    },
    # 1d 123
    # 1 123
    re.compile(r"^(\d+)(?:d\s*|\s+)(\d+)$"): {
        H_M: lambda d, m: total_secs(days=d, mins=m),
        D_H: lambda d, h: total_secs(days=d, hours=h),
        D_H_M: lambda d, m: total_secs(days=d, mins=m),
        D_H_M_NO_COLONS: lambda d, m: total_secs(days=d, mins=m),
        "default": lambda d, s: total_secs(days=d, secs=s),
    },
    # 1d 12.134
    # 1 12.134
    re.compile(r"^(\d+)(?:d\s*|\s+)(\d+.\d+)$"): {
        "default": lambda d, s: total_secs(days=d, secs=s),
    },
    # 123
    re.compile(r"^(\d+)$"): {
        H_M: lambda m: total_secs(mins=float(m)),
        D_H: lambda h: total_secs(hours=float(h)),
        D_H_M: lambda m: total_secs(mins=float(m)),
        D_H_M_NO_COLONS: lambda m: total_secs(mins=m),
        "default": lambda s: total_secs(secs=s),
    },
    # 11.123
    re.compile(r"^(\d+.\d+)$"): {
        "default": lambda s: total_secs(secs=s),
    },
}


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


def parse_duration_value(formatted_value: str, format: str) -> float:
    """
    Parses a formatted duration string into a number of seconds according to the
    provided format. If the format doesn't match exactly, it will still try to
    parse it as best as possible.

    :param formatted_value: The formatted duration string.
    :param format: The format of the duration string.
    :return: The total number of seconds for the given formatted duration.
    :raises ValueError: If the format is invalid.
    """

    if format not in DURATION_FORMATS:
        raise ValueError(f"{format} is not a valid duration format.")
    # support for negative values
    multiplier = 1
    if formatted_value.startswith("-"):
        formatted_value = formatted_value[1:]
        multiplier = -1

    for regex, format_funcs in DURATION_REGEXPS.items():
        match = regex.match(formatted_value)
        if match:
            format_func = format_funcs.get(format, format_funcs["default"])
            # handle named groups in regexps
            captured = match.groupdict()
            if any(v for v in captured.values()):
                return format_func(**captured) * multiplier
            # if no named groups, use standard args
            try:
                return format_func(*match.groups()) * multiplier
            # invalid number of args
            except TypeError:
                pass

    # If it's not one of the known formats, try to parse it as a postgres interval
    # Lookups formula save duration in the postgres interval format in the database.
    total_seconds = postgres_interval_to_seconds(formatted_value)
    if total_seconds is not None:
        return total_seconds

    raise ValueError(f"{formatted_value} is not a valid duration string.")


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


def get_duration_search_expression(field) -> Func:
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
    from psycopg.types.datetime import IntervalLoader  # noqa: BPG001

    from baserow.core.psycopg import psycopg

    class BaserowIntervalLoader(IntervalLoader):
        """
        We're not doing anything special here, but if we don't register this
        adapter tests will fail when parsing negative intervals.
        """

        def load(self, data):
            return super().load(data)

    psycopg.adapters.register_loader("interval", BaserowIntervalLoader)
