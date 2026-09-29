from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from baserow.contrib.integrations.core.constants import (
    PERIODIC_INTERVAL_DAY,
    PERIODIC_INTERVAL_HOUR,
    PERIODIC_INTERVAL_MINUTE,
    PERIODIC_INTERVAL_WEEK,
)
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


def test_calculate_next_periodic_run_keeps_local_time_across_dst():
    """
    A weekly schedule of "every Monday at 09:00 in Amsterdam" must stay at 09:00
    local on both sides of a DST transition. Amsterdam is UTC+1 in winter and
    UTC+2 in summer, so the same local time is a different instant in each.
    """

    winter = calculate_next_periodic_run(
        interval=PERIODIC_INTERVAL_WEEK,
        minute=0,
        hour=9,
        day_of_week=0,  # Monday
        day_of_month=1,
        from_time=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        tz="Europe/Amsterdam",
    )
    # 09:00 in Amsterdam is 08:00 UTC while the clocks are on CET.
    assert winter == datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc)
    assert winter.astimezone(ZoneInfo("Europe/Amsterdam")).hour == 9

    summer = calculate_next_periodic_run(
        interval=PERIODIC_INTERVAL_WEEK,
        minute=0,
        hour=9,
        day_of_week=0,  # Monday
        day_of_month=1,
        from_time=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
        tz="Europe/Amsterdam",
    )
    # The same 09:00 is 07:00 UTC once the clocks go forward onto CEST.
    assert summer == datetime(2026, 7, 6, 7, 0, tzinfo=timezone.utc)
    assert summer.astimezone(ZoneInfo("Europe/Amsterdam")).hour == 9


def test_calculate_next_periodic_run_keeps_local_day_across_dst():
    """
    A schedule near midnight must keep the weekday the user chose. Monday 00:30 in
    Amsterdam is the previous Sunday in UTC, so a frozen UTC offset would move the
    run onto a Sunday once the clocks changed.
    """

    for from_time, expected in [
        # Summer, CEST: Monday 00:30 local is 22:30 UTC on the Sunday.
        (
            datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 5, 22, 30, tzinfo=timezone.utc),
        ),
        # Winter, CET: the same local time is 23:30 UTC on the Sunday.
        (
            datetime(2026, 12, 9, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 12, 13, 23, 30, tzinfo=timezone.utc),
        ),
    ]:
        next_run = calculate_next_periodic_run(
            interval=PERIODIC_INTERVAL_WEEK,
            minute=30,
            hour=0,
            day_of_week=0,  # Monday
            day_of_month=1,
            from_time=from_time,
            tz="Europe/Amsterdam",
        )
        assert next_run == expected
        local = next_run.astimezone(ZoneInfo("Europe/Amsterdam"))
        assert (local.weekday(), local.hour, local.minute) == (0, 0, 30)


def test_calculate_next_periodic_run_defaults_to_utc():
    """
    Without a timezone the schedule fields are UTC, which is what services created
    before the schedule became timezone aware rely on.
    """

    next_run = calculate_next_periodic_run(
        interval=PERIODIC_INTERVAL_WEEK,
        minute=0,
        hour=9,
        day_of_week=0,
        day_of_month=1,
        from_time=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
    )
    assert next_run == datetime(2026, 7, 6, 9, 0, tzinfo=timezone.utc)


def test_calculate_next_periodic_run_handles_dst_gap_and_overlap():
    """
    The two days a year where a local time is undefined must still resolve to a
    single instant rather than raising.
    """

    # Spring forward: on 2026-03-29 Amsterdam jumps 02:00 -> 03:00, so a daily
    # 02:30 doesn't exist that day and resolves to the equivalent instant after.
    gap = calculate_next_periodic_run(
        interval=PERIODIC_INTERVAL_DAY,
        minute=30,
        hour=2,
        day_of_week=0,
        day_of_month=1,
        from_time=datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc),
        tz="Europe/Amsterdam",
    )
    assert gap == datetime(2026, 3, 29, 1, 30, tzinfo=timezone.utc)

    # Fall back: on 2026-10-25 Amsterdam repeats 02:00 -> 03:00, so a daily 02:30
    # happens twice and resolves to the first of the two.
    overlap = calculate_next_periodic_run(
        interval=PERIODIC_INTERVAL_DAY,
        minute=30,
        hour=2,
        day_of_week=0,
        day_of_month=1,
        from_time=datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc),
        tz="Europe/Amsterdam",
    )
    assert overlap == datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc)


def test_calculate_next_periodic_run_minute_interval_ignores_timezone():
    """
    A MINUTE interval is a frequency, so it must advance by real elapsed time even
    when the local clock does something unusual. During a fall-back overlap the
    local clock repeats an hour, which would turn "every 15 minutes" into a 75
    minute gap if the interval were advanced on the wall clock.
    """

    # 2026-10-25 is the fall-back in Amsterdam: 03:00 CEST repeats as 02:00 CET.
    # This run lands at 02:50 CEST, inside the hour that is about to repeat.
    from_time = datetime(2026, 10, 25, 0, 50, tzinfo=timezone.utc)

    next_run = calculate_next_periodic_run(
        interval=PERIODIC_INTERVAL_MINUTE,
        minute=15,
        hour=0,
        day_of_week=0,
        day_of_month=1,
        from_time=from_time,
        tz="Europe/Amsterdam",
    )

    assert next_run == datetime(2026, 10, 25, 1, 5, tzinfo=timezone.utc)
    assert (next_run - from_time) == timedelta(minutes=15)


def test_calculate_next_periodic_run_hour_interval_ignores_timezone():
    """
    An HOUR interval only picks a minute past the hour, so it's calculated in UTC
    and a timezone must not shift it.
    """

    from_time = datetime(2026, 7, 1, 10, 45, tzinfo=timezone.utc)

    for tz in ["UTC", "Europe/Amsterdam", "Asia/Kolkata"]:
        next_run = calculate_next_periodic_run(
            interval=PERIODIC_INTERVAL_HOUR,
            minute=30,
            hour=0,
            day_of_week=0,
            day_of_month=1,
            from_time=from_time,
            tz=tz,
        )
        assert next_run == datetime(2026, 7, 1, 11, 30, tzinfo=timezone.utc)


def test_calculate_next_periodic_run_without_an_interval_has_no_next_run():
    """
    A schedule with no interval hasn't been configured, so there's no next run to
    calculate. Returning a time anyway is what previously made an unconfigured
    trigger due, and it then ran every hour off the unknown-interval fallback.
    """

    assert (
        calculate_next_periodic_run(
            interval=None,
            minute=0,
            hour=9,
            day_of_week=0,
            day_of_month=1,
            from_time=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
            tz="Europe/Amsterdam",
        )
        is None
    )
