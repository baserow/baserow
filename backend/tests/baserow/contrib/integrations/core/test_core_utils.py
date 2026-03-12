import pytest

from baserow.contrib.integrations.core.utils import calculate_next_periodic_run

from .cases.core_periodic_service_type import PERIODIC_SERVICE_CALCULATE_NEXT_RUN_CASES


@pytest.mark.parametrize(
    "interval,minute,hour,day_of_week,day_of_month,from_time,expected_next_run",
    PERIODIC_SERVICE_CALCULATE_NEXT_RUN_CASES,
)
def test_calculate_next_periodic_run(
    interval, minute, hour, day_of_week, day_of_month, from_time, expected_next_run
):
    result = calculate_next_periodic_run(
        interval=interval,
        minute=minute,
        hour=hour,
        day_of_week=day_of_week,
        day_of_month=day_of_month,
        from_time=from_time,
    )
    assert result == expected_next_run
