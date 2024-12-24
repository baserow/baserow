from datetime import date, datetime

from django.core.exceptions import ValidationError

import pytest

from baserow.core.formula.validator import ensure_date, ensure_datetime


def test_ensure_date():
    assert ensure_date(None) is None
    assert ensure_date("2024-12-17") == date(2024, 12, 17)
    with pytest.raises(ValidationError) as exc:
        ensure_date("invalid")
    assert exc.value.args[0] == "Value cannot be converted to a date."


def test_ensure_datetime():
    assert ensure_datetime(None) is None
    assert ensure_datetime("2024-12-17 12:00") == datetime(2024, 12, 17, 12, 0, 0)
    with pytest.raises(ValidationError) as exc:
        ensure_datetime("invalid")
    assert exc.value.args[0] == "Value cannot be converted to a datetime."
