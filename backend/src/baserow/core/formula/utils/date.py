import re

from baserow.core.duration import parse_duration_string as parse_duration_string

MOMENT_FORMAT_MAP = {
    "YYYY": "%Y",
    "YY": "%y",
    "MMMM": "%B",
    "MMM": "%b",
    "MM": "%m",
    "M": "%-m",
    "DD": "%d",
    "D": "%-d",
    "dddd": "%A",
    "ddd": "%a",
    "HH": "%H",
    "H": "%-H",
    "hh": "%I",
    "h": "%-I",
    "mm": "%M",
    "m": "%-M",
    "ss": "%S",
    "s": "%-S",
    "A": "%p",
    "a": "%p",
    "SSS": "%f",
}
RE_SUPPORTED_MOMENT_TOKEN = re.compile(
    "|".join(sorted(MOMENT_FORMAT_MAP.keys(), key=len, reverse=True))
)

# Extends the conversion regex with T, the ISO 8601 date-time separator, which
# is a valid literal in Moment.js format strings but has no mapped Python token.
RE_VALID_FORMAT = re.compile(
    "|".join(sorted(MOMENT_FORMAT_MAP.keys(), key=len, reverse=True)) + "|T"
)


def is_valid_datetime_format(value: str) -> bool:
    """Return True if the string contains only supported Moment.js format tokens."""

    if not isinstance(value, str):
        return False

    # An empty string is not a valid datetime format
    if not value:
        return False

    stripped = RE_VALID_FORMAT.sub("", value)
    return not re.search(r"[a-zA-Z]", stripped)


def convert_date_format_moment_to_python(moment_format: str) -> str:
    """
    Convert a Moment.js datetime string to the Python strftime equivalent.

    :param moment_format: The Moment.js format, e.g. 'YYYY-MM-DD'
    :return: The Python datetime equivalent, e.g. '%Y-%m-%d'
    """

    def replace_token(match: re.Match) -> str:
        return MOMENT_FORMAT_MAP[match.group(0)]

    return RE_SUPPORTED_MOMENT_TOKEN.sub(replace_token, moment_format)
