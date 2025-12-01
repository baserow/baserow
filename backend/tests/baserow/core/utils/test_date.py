import pytest

from baserow.core.formula.utils.date import convert_date_format_moment_to_python


@pytest.mark.parametrize(
    "moment_format,python_format",
    [
        ("YYYY", "%Y"),
        ("YY", "%y"),
        ("MMMM", "%B"),
        ("MMM", "%b"),
        ("MM", "%m"),
        ("M", "%-m"),
        ("DD", "%d"),
        ("D", "%-d"),
        ("dddd", "%A"),
        ("ddd", "%a"),
        ("HH", "%H"),
        ("H", "%-H"),
        ("hh", "%I"),
        ("h", "%-I"),
        ("mm", "%M"),
        ("m", "%-M"),
        ("ss", "%S"),
        ("s", "%-S"),
        ("A", "%p"),
        ("a", "%p"),
        ("SSS", "%f"),
        ("", ""),
        ("foo", "foo"),
        # Some common formats
        ("YYYY-MM-DD", "%Y-%m-%d"),
        ("YYYY-MM-DD[T]HH:mm:ss", "%Y-%m-%d[T]%H:%M:%S"),
        ("DD/MM/YYYY HH:mm:ss", "%d/%m/%Y %H:%M:%S"),
        ("ddd, MMM D, YYYY h:mm A", "%a, %b %-d, %Y %-I:%M %p"),
        ("MMMM D, YYYY", "%B %-d, %Y"),
        ("MM-DD-YYYY", "%m-%d-%Y"),
        ("HH:mm:ss", "%H:%M:%S"),
        ("hh:mm A", "%I:%M %p"),
        ("H:m:s", "%-H:%-M:%-S"),
        ("h:m A", "%-I:%-M %p"),
        # Ensure longer tokens are replaced correctly
        ("MMMM MMM MM M", "%B %b %m %-m"),
        ("YYYY-MM-DD YYYY", "%Y-%m-%d %Y"),
        ("HH:mm HH:mm", "%H:%M %H:%M"),
        ("DD DD DD", "%d %d %d"),
    ],
)
def test_convert_date_format_moment_to_python(moment_format, python_format):
    assert convert_date_format_moment_to_python(moment_format) == python_format
