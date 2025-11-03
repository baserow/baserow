import re


def convert_date_format_moment_to_python(moment_format: str) -> str:
    """
    Convert a Moment.js datetime string to the Python strftime equivalent.

    :param moment_format: The Moment.js format, e.g. 'YYYY-MM-DD'
    :return: The Python datetime equivalent, e.g. '%Y-%m-%d'
    """

    format_map = {
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
        # Moment's SSS is milliseconds, whereas Python's %f is microseconds
        "SSS": "%f",
    }

    # Sort longest tokens first so 'MMMM' matches before 'MM', etc.
    tokens = sorted(format_map.keys(), key=len, reverse=True)

    # Build a regex, e.g. re.compile("YYYY|YY")
    pattern = re.compile("|".join(token for token in tokens))

    def replace_token(match: re.Match) -> str:
        """Replace a matched Moment token with its Python equivalent."""

        token = match.group(0)
        return format_map[token]

    return pattern.sub(replace_token, moment_format)
