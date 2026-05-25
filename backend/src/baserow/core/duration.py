import re
from datetime import timedelta
from typing import Optional, Union

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

DURATION_PATTERNS = [
    (re.compile(r"^(\d+)\s+years?$", re.IGNORECASE), "days", 365),
    (re.compile(r"^(\d+)\s+months?$", re.IGNORECASE), "days", 30),
    (re.compile(r"^(\d+)\s+weeks?$", re.IGNORECASE), "weeks", 1),
    (re.compile(r"^(\d+)\s+days?$", re.IGNORECASE), "days", 1),
    (re.compile(r"^(\d+)\s+hours?$", re.IGNORECASE), "hours", 1),
    (re.compile(r"^(\d+)\s+minutes?$", re.IGNORECASE), "minutes", 1),
    (re.compile(r"^(\d+)\s+seconds?$", re.IGNORECASE), "seconds", 1),
]


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
# web-frontend/modules/core/utils/duration.js:DURATION_REGEXPS
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


def parse_duration_string(value: str) -> Optional[timedelta]:
    """Parse a duration string into a timedelta, or None if invalid."""

    if not isinstance(value, str):
        return None
    if value.strip() == "":
        return None

    try:
        total_seconds = parse_duration_value(value, MOST_ACCURATE_DURATION_FORMAT)
        return timedelta(seconds=round(total_seconds, 3))
    except (ValueError, OverflowError):
        pass

    for pattern, unit, factor in DURATION_PATTERNS:
        match = pattern.match(value.strip())
        if match:
            amount = int(match.group(1)) * factor
            return timedelta(**{unit: amount})

    return None
