import re
from datetime import timedelta

import pytest

from baserow.core.duration import (
    format_value_with_duration_format,
    is_valid_duration_format,
    parse_value_with_duration_format,
    tokenize_duration_format,
)


class TestTokenizeDurationFormat:
    @pytest.mark.parametrize(
        "format_str,value,expected_fields,expected_groups",
        [
            ("h:mm", "1:30", ["hours", "minutes"], ("1", "30")),
            # literal `:` separators are escaped
            (
                "h:mm:ss",
                "1:23:45",
                ["hours", "minutes", "seconds"],
                ("1", "23", "45"),
            ),
            # space-separated tokens
            (
                "d h mm ss",
                "2 3 04 05",
                ["days", "hours", "minutes", "seconds"],
                ("2", "3", "04", "05"),
            ),
            # two-char tokens take precedence over one-char (hh, not h+h)
            ("hh:mm", "12:34", ["hours", "minutes"], ("12", "34")),
            # arbitrary literal chars (avoid d/h/m/s, which are token letters)
            ("d|h.", "2|5.", ["days", "hours"], ("2", "5")),
            # leading minus is optional
            ("h:mm", "-1:30", ["hours", "minutes"], ("1", "30")),
            # fractional-seconds run with a dot separator
            (
                "h:mm:ss.fff",
                "1:23:45.678",
                ["hours", "minutes", "seconds", "fraction"],
                ("1", "23", "45", "678"),
            ),
            # single `f` accepts a single fractional digit
            (
                "ss.f",
                "45.6",
                ["seconds", "fraction"],
                ("45", "6"),
            ),
            # the separator before `f` is a literal, so non-dot delimiters work
            (
                "s fff",
                "1 234",
                ["seconds", "fraction"],
                ("1", "234"),
            ),
            (
                "mm:ss,ff",
                "01:02,34",
                ["minutes", "seconds", "fraction"],
                ("01", "02", "34"),
            ),
            # backslash escapes a token letter so it becomes a literal suffix:
            # `d\d h\h` matches "1d 2h" (the d/h after the backslash are literal)
            (
                r"d\d h\h",
                "1d 2h",
                ["days", "hours"],
                ("1", "2"),
            ),
            (
                r"d\d h\h mm\m ss\s",
                "1d 2h 03m 04s",
                ["days", "hours", "minutes", "seconds"],
                ("1", "2", "03", "04"),
            ),
            # an escaped backslash is a literal backslash
            (
                r"h\\mm",
                "1\\23",
                ["hours", "minutes"],
                ("1", "23"),
            ),
            # an escaped `f` is a literal `f`, not the fraction token, so a real
            # fraction can still follow and its precision is read correctly
            (
                r"\f ss.ff",
                "f 01.50",
                ["seconds", "fraction"],
                ("01", "50"),
            ),
        ],
    )
    def test_tokenizes_valid_format(
        self, format_str, value, expected_fields, expected_groups
    ):
        result = tokenize_duration_format(format_str)

        assert result is not None
        regex, fields = result
        assert isinstance(regex, re.Pattern)
        assert fields == expected_fields
        match = regex.match(value)
        assert match is not None
        assert match.groups() == expected_groups

    @pytest.mark.parametrize(
        "format_str,value",
        [
            # anchored to start of string
            ("h:mm", "prefix 1:30"),
            # anchored to end of string
            ("h:mm", "1:30 trailing"),
            # literal mismatch (`|` in format, `/` in value)
            ("d|h.", "2/5."),
        ],
    )
    def test_value_does_not_match_format(self, format_str, value):
        regex, _ = tokenize_duration_format(format_str)

        assert regex.match(value) is None

    @pytest.mark.parametrize(
        "format_str",
        [
            "h:mm:h",  # h repeated
            "mm mm",  # mm repeated
            "h hh",  # h then hh — both map to "hours"
            "ss s",  # ss then s — both map to "seconds"
            "ss.f.f",  # fraction run appears twice
            "f.fff",  # fraction run appears twice
        ],
    )
    def test_repeated_tokens_are_invalid(self, format_str):
        assert tokenize_duration_format(format_str) is None

    @pytest.mark.parametrize(
        "format_str",
        [
            "",
            ":::",  # only literals, no token
            "   ",  # only whitespace, no token
        ],
    )
    def test_format_with_no_tokens_is_invalid(self, format_str):
        assert tokenize_duration_format(format_str) is None

    @pytest.mark.parametrize(
        "format_str",
        [
            "h:mm\\",  # trailing backslash has nothing to escape
            "\\",  # lone backslash
        ],
    )
    def test_trailing_backslash_is_invalid(self, format_str):
        assert tokenize_duration_format(format_str) is None

    @pytest.mark.parametrize("value", [None, 1, 1.5, [], {}, object()])
    def test_non_string_input_returns_none(self, value):
        assert tokenize_duration_format(value) is None


class TestIsValidDurationFormat:
    @pytest.mark.parametrize(
        "format_str",
        [
            "h:mm",
            "h:mm:ss",
            "d h:mm:ss",
            "d h mm ss",
            "d",
            "hh:mm:ss",
            "h:mm:ss.f",
            "h:mm:ss.ff",
            "h:mm:ss.fff",
            "s fff",
        ],
    )
    def test_returns_true_for_valid_formats(self, format_str):
        assert is_valid_duration_format(format_str) is True

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "h:h",  # repeated token
            ":::",  # only literals
            None,
            123,
            [],
            {},
        ],
    )
    def test_returns_false_for_invalid_inputs(self, value):
        assert is_valid_duration_format(value) is False


class TestParseValueWithDurationFormat:
    @pytest.mark.parametrize(
        "value,format_str,expected",
        [
            ("1:30", "h:mm", timedelta(hours=1, minutes=30)),
            ("1:23:45", "h:mm:ss", timedelta(hours=1, minutes=23, seconds=45)),
            (
                "2 3:04:05",
                "d h:mm:ss",
                timedelta(days=2, hours=3, minutes=4, seconds=5),
            ),
            ("3 4", "d h", timedelta(days=3, hours=4)),
            ("-1:30", "h:mm", -timedelta(hours=1, minutes=30)),
            # surrounding whitespace is stripped
            ("  1:30  ", "h:mm", timedelta(hours=1, minutes=30)),
            ("0:00", "h:mm", timedelta(0)),
            # negative zero is still zero
            ("-0:00", "h:mm", timedelta(0)),
            # the generated regex uses \d+ for every field, so single-digit
            # values are accepted even where the format suggests two digits
            ("1:5", "h:mm", timedelta(hours=1, minutes=5)),
            # "hh:mm" tokenizes as hh + mm, not h + h + mm
            ("12:34", "hh:mm", timedelta(hours=12, minutes=34)),
            # 25 hours rolls over into 1d 1h in the resulting timedelta
            ("25:00", "h:mm", timedelta(days=1, hours=1)),
            # fractional seconds: digits are a positional decimal
            (
                "1:23:45.678",
                "h:mm:ss.fff",
                timedelta(hours=1, minutes=23, seconds=45, milliseconds=678),
            ),
            # "5" at precision 1 is 0.5s, not 0.05s
            ("0:00:00.5", "h:mm:ss.f", timedelta(milliseconds=500)),
            # "05" is 0.05s
            ("0:00:00.05", "h:mm:ss.ff", timedelta(milliseconds=50)),
            # non-dot separator before the fraction
            ("1 234", "s fff", timedelta(seconds=1, milliseconds=234)),
            # negative carries the sub-second component
            (
                "-0:00:01.250",
                "h:mm:ss.fff",
                -timedelta(seconds=1, milliseconds=250),
            ),
        ],
    )
    def test_parses_valid_values(self, value, format_str, expected):
        assert parse_value_with_duration_format(value, format_str) == expected

    @pytest.mark.parametrize(
        "value,format_str",
        [
            # value doesn't match the format's literal separator
            ("1.30", "h:mm"),
            # value has trailing garbage
            ("1:30 extra", "h:mm"),
            # non-string values
            (None, "h:mm"),
            (1, "h:mm"),
            (1.5, "h:mm"),
            ([], "h:mm"),
            ({}, "h:mm"),
            # invalid format strings
            ("1:30", None),
            ("1:30", ""),
            ("1:30", "h:h"),
            ("1:30", 123),
            ("1:30", ":::"),
        ],
    )
    def test_returns_none_for_invalid_input(self, value, format_str):
        assert parse_value_with_duration_format(value, format_str) is None


class TestFormatValueWithDurationFormat:
    @pytest.mark.parametrize(
        "duration,format_str,expected",
        [
            (timedelta(hours=1, minutes=30), "h:mm", "1:30"),
            (
                timedelta(hours=1, minutes=23, seconds=45),
                "h:mm:ss",
                "1:23:45",
            ),
            (
                timedelta(days=2, hours=3, minutes=4, seconds=5),
                "d h:mm:ss",
                "2 3:04:05",
            ),
            (timedelta(days=3, hours=4), "d h", "3 4"),
            # h-only rollup: 1d 2h → 26 total hours
            (timedelta(days=1, hours=2), "h", "26"),
            # mm-only rollup: 1h 30m → 90 total minutes (zero-padded by mm)
            (timedelta(hours=1, minutes=30), "mm", "90"),
            # mm:ss rollup: 1h 30m → 90 minutes, 0 seconds
            (timedelta(hours=1, minutes=30), "mm:ss", "90:00"),
            # ss-only rollup: 5m → 300 total seconds
            (timedelta(minutes=5), "ss", "300"),
            # within-day hours when d is present: 25h → 1d 1h
            (timedelta(hours=25, minutes=30), "d h:mm", "1 1:30"),
            # without d, hours roll up: 25h → 25 total hours
            (timedelta(hours=25, minutes=30), "h:mm", "25:30"),
            # negative values get a leading minus
            (-timedelta(hours=1, minutes=30), "h:mm", "-1:30"),
            (-timedelta(hours=1, minutes=30), "mm:ss", "-90:00"),
            # zero in every position
            (timedelta(0), "h:mm", "0:00"),
            (timedelta(0), "d h:mm:ss", "0 0:00:00"),
            # two-char tokens are zero-padded; one-char tokens are not
            (timedelta(hours=1, minutes=5), "h:mm", "1:05"),
            (timedelta(hours=1, minutes=5), "hh:mm", "01:05"),
            # arbitrary literal chars are preserved
            (timedelta(days=2, hours=5), "d|h.", "2|5."),
            # integer-second formats (no fraction token) round to whole seconds
            # rather than truncating: 1.5s -> "2", 1.4s -> "1"
            (timedelta(seconds=1, milliseconds=500), "s", "2"),
            (timedelta(seconds=1, milliseconds=400), "s", "1"),
            # rounding is half away from zero, so 0.5s -> "1" (not "0")
            (timedelta(milliseconds=500), "s", "1"),
            (-timedelta(milliseconds=500), "s", "-1"),
            # integer rounding carries across fields: 59.6s -> 1:00
            (timedelta(seconds=59, milliseconds=600), "mm:ss", "01:00"),
            # 59m 59.6s -> 1:00:00
            (
                timedelta(minutes=59, seconds=59, milliseconds=600),
                "h:mm:ss",
                "1:00:00",
            ),
            # fractional seconds rendered zero-padded to the format precision
            (
                timedelta(hours=1, minutes=23, seconds=45, milliseconds=678),
                "h:mm:ss.fff",
                "1:23:45.678",
            ),
            # 0.5s at precision 1 -> "5"; at precision 3 -> "500"
            (timedelta(milliseconds=500), "ss.f", "00.5"),
            (timedelta(milliseconds=500), "ss.fff", "00.500"),
            # 0.05s -> "05" at precision 2
            (timedelta(milliseconds=50), "ss.ff", "00.05"),
            # non-dot separator preserved on output
            (timedelta(seconds=1, milliseconds=234), "s fff", "1 234"),
            # rounding up carries across fields: 59.9996 -> 1:00.000
            (
                timedelta(seconds=59, microseconds=999600),
                "mm:ss.fff",
                "01:00.000",
            ),
            # carry that rolls all the way over: 59:59.9996 -> 1:00:00.000
            (
                timedelta(minutes=59, seconds=59, microseconds=999600),
                "h:mm:ss.fff",
                "1:00:00.000",
            ),
            # values beyond the precision are rounded, not truncated
            (
                timedelta(seconds=1, microseconds=236000),
                "ss.ff",
                "01.24",
            ),
            # negative fractional value keeps the sign
            (
                -timedelta(seconds=1, milliseconds=250),
                "ss.fff",
                "-01.250",
            ),
            # escaped token letters are emitted as literal unit suffixes
            (timedelta(days=1, hours=2), r"d\d h\h", "1d 2h"),
            (
                timedelta(days=1, hours=2, minutes=3, seconds=4),
                r"d\d h\h mm\m ss\s",
                "1d 2h 03m 04s",
            ),
            (timedelta(days=1, hours=2, minutes=34), r"d\d h:mm", "1d 2:34"),
            # escaped backslash renders as a literal backslash
            (timedelta(hours=1, minutes=5), r"h\\mm", "1\\05"),
            # escaped `f` literal alongside a real fraction (precision read as 2)
            (timedelta(seconds=1, milliseconds=500), r"\f ss.ff", "f 01.50"),
        ],
    )
    def test_formats_valid_durations(self, duration, format_str, expected):
        assert format_value_with_duration_format(duration, format_str) == expected

    @pytest.mark.parametrize(
        "duration,format_str",
        [
            # non-timedelta values
            (None, "h:mm"),
            (1, "h:mm"),
            (1.5, "h:mm"),
            ("1:30", "h:mm"),
            ([], "h:mm"),
            ({}, "h:mm"),
            # invalid format strings
            (timedelta(hours=1), None),
            (timedelta(hours=1), ""),
            (timedelta(hours=1), "h:h"),
            (timedelta(hours=1), 123),
            (timedelta(hours=1), ":::"),
        ],
    )
    def test_returns_none_for_invalid_input(self, duration, format_str):
        assert format_value_with_duration_format(duration, format_str) is None

    @pytest.mark.parametrize(
        "duration,format_str",
        [
            (timedelta(hours=1, minutes=30), "h:mm"),
            (timedelta(hours=1, minutes=23, seconds=45), "h:mm:ss"),
            (
                timedelta(days=2, hours=3, minutes=4, seconds=5),
                "d h:mm:ss",
            ),
            (-timedelta(hours=1, minutes=30), "h:mm"),
            (timedelta(hours=25, minutes=30), "h:mm"),
            (timedelta(hours=1, minutes=30), "mm:ss"),
            # fractional formats round-trip when the value fits the precision
            (
                timedelta(hours=1, minutes=23, seconds=45, milliseconds=678),
                "h:mm:ss.fff",
            ),
            (timedelta(seconds=1, milliseconds=500), "ss.f"),
            (timedelta(seconds=1, milliseconds=234), "s fff"),
            (-timedelta(seconds=1, milliseconds=250), "ss.fff"),
            # escaped literal unit suffixes round-trip
            (timedelta(days=1, hours=2), r"d\d h\h"),
            (timedelta(days=1, hours=2, minutes=3, seconds=4), r"d\d h\h mm\m ss\s"),
        ],
    )
    def test_parsed_format_returns_correct_duration(self, duration, format_str):
        formatted = format_value_with_duration_format(duration, format_str)
        assert parse_value_with_duration_format(formatted, format_str) == duration
