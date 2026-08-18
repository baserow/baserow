import pytest

from baserow.config.settings.utils import str_to_bool


@pytest.mark.parametrize(
    "value,expected",
    [
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("yes", True),
        ("1", True),
        ("on", True),
        ("y", True),
        ("t", True),
        ("false", False),
        ("False", False),
        ("FALSE", False),
        ("no", False),
        ("0", False),
        ("off", False),
        ("n", False),
        ("", False),
        ("  ", False),
        ("anything-else", False),
    ],
)
def test_str_to_bool(value, expected):
    assert str_to_bool(value) is expected
