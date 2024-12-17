import pytest
from freezegun import freeze_time

from baserow.core.datetime import get_current_hourly_quarter


@pytest.mark.parametrize(
    "minutes,output",
    [
        (00, 0),
        (15, 1),
        (30, 2),
        (45, 3),
        (59, 3),
    ],
)
def test_get_current_hourly_quarter(minutes, output):
    with freeze_time(f"2024-12-16 12:{minutes}"):
        assert get_current_hourly_quarter() == output
