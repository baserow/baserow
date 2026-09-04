from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone
from typing import Optional
from zoneinfo import ZoneInfo

from django.utils import timezone

from dateutil.relativedelta import relativedelta

from baserow.contrib.integrations.core.constants import (
    PERIODIC_INTERVAL_DAY,
    PERIODIC_INTERVAL_HOUR,
    PERIODIC_INTERVAL_MINUTE,
    PERIODIC_INTERVAL_MONTH,
    PERIODIC_INTERVAL_WEEK,
    PERIODIC_TIMEZONE_DEFAULT,
)


def calculate_next_periodic_run(
    interval: Optional[str],
    minute: int,
    hour: int,
    day_of_week: int,
    day_of_month: int,
    from_time: Optional[datetime] = None,
    tz: Optional[str] = PERIODIC_TIMEZONE_DEFAULT,
) -> Optional[datetime]:
    """
    Calculate the next scheduled run time based on the service's schedule configuration.

    A schedule with no interval hasn't been configured yet, so it has no next run
    and `None` is returned. Inventing one would mean an unconfigured service gets
    dispatched despite the user never having chosen when it should run.

    The DAY, WEEK and MONTH intervals pick a wall clock time, so they're calculated
    in `tz` and the result converted back to UTC. This is what keeps them on their
    local time across a DST transition: resolving the offset for each occurrence
    gives "every Monday at 09:00 in Amsterdam", whereas resolving it once when the
    schedule is saved only gives "every Monday at 08:00 UTC", which stops meaning
    09:00 the moment the clocks change.

    MINUTE and HOUR ignore `tz` and are calculated in UTC. MINUTE is a frequency
    rather than a time of day, so it has to advance by real elapsed time: in a
    fall-back overlap the local clock repeats an hour, which would turn "every 15
    minutes" into a 75 minute gap. HOUR only picks a minute past the hour, and
    every DST shift is a whole number of hours, so it can't be affected either.

    On the two days a year where a local time is undefined, the standard library
    defaults apply: a time in a spring-forward gap resolves to the equivalent
    instant after the transition, and an ambiguous time in a fall-back overlap
    resolves to its first occurrence.

    :param interval: The interval type (MINUTE, HOUR, DAY, WEEK, MONTH), or `None`
        if it hasn't been chosen yet
    :param minute: The minute value (0-59)
    :param hour: The hour value (0-23)
    :param day_of_week: The day of week (0=Monday, 6=Sunday)
    :param day_of_month: The day of month (1-31)
    :param from_time: Calculate next run from this time (defaults to now)
    :param tz: The IANA timezone the schedule fields are expressed in
    :return: The next scheduled run time in UTC, or `None` if there's no interval
    """

    if not interval:
        return None

    if from_time is None:
        from_time = timezone.now()

    schedules_a_local_time = interval in [
        PERIODIC_INTERVAL_DAY,
        PERIODIC_INTERVAL_WEEK,
        PERIODIC_INTERVAL_MONTH,
    ]
    zone = (
        ZoneInfo(tz or PERIODIC_TIMEZONE_DEFAULT)
        if schedules_a_local_time
        else datetime_timezone.utc
    )

    # A naive `from_time` can't be converted, so it's assumed to already be UTC.
    if timezone.is_naive(from_time):
        from_time = from_time.replace(tzinfo=datetime_timezone.utc)

    # The calculation below is wall clock arithmetic, so it runs on a naive time in
    # `zone`. Staying naive means a DST transition can't silently turn a `replace()`
    # or a `timedelta` into an absolute-time operation part way through.
    from_time = from_time.astimezone(zone).replace(second=0, microsecond=0, tzinfo=None)

    if interval == PERIODIC_INTERVAL_MINUTE:
        # For minute intervals, add the interval to the from_time
        interval_minutes = minute if minute > 0 else 1
        next_run = from_time + timedelta(minutes=interval_minutes)

    elif interval == PERIODIC_INTERVAL_HOUR:
        # Run at the specified minute of each hour
        next_run = from_time.replace(minute=minute)
        # If we've already passed this minute in the current hour, move to next hour
        if next_run <= from_time:
            next_run += timedelta(hours=1)

    elif interval == PERIODIC_INTERVAL_DAY:
        # Run at the specified hour:minute each day
        next_run = from_time.replace(hour=hour, minute=minute)
        # If we've already passed this time today, move to tomorrow
        if next_run <= from_time:
            next_run += timedelta(days=1)

    elif interval == PERIODIC_INTERVAL_WEEK:
        # Run at the specified day_of_week at hour:minute each week
        current_weekday = from_time.weekday()
        days_ahead = day_of_week - current_weekday

        if days_ahead < 0:  # Target day already happened this week
            days_ahead += 7
        elif days_ahead == 0:  # Target day is today
            # Check if we've already passed the scheduled time
            scheduled_time_today = from_time.replace(hour=hour, minute=minute)
            if scheduled_time_today <= from_time:
                days_ahead = 7  # Move to next week

        next_run = from_time + timedelta(days=days_ahead)
        next_run = next_run.replace(hour=hour, minute=minute)

    elif interval == PERIODIC_INTERVAL_MONTH:
        # Run at the specified day_of_month at hour:minute each month.
        # Handle case where day_of_month doesn't exist in the current month
        # (e.g., day 30 in February) by using the last day of the month.
        try:
            next_run = from_time.replace(day=day_of_month, hour=hour, minute=minute)
        except ValueError:
            # Use last day of the current month
            next_run = from_time.replace(day=1) + relativedelta(months=1, days=-1)
            next_run = next_run.replace(hour=hour, minute=minute)

        # If we've already passed this time this month, move to next month
        if next_run <= from_time:
            next_run += relativedelta(months=1)
            # Handle case where day_of_month doesn't exist in the target month
            try:
                next_run = next_run.replace(day=day_of_month)
            except ValueError:
                # Use last day of the target month
                next_run = next_run.replace(day=1) + relativedelta(months=1, days=-1)
                next_run = next_run.replace(hour=hour, minute=minute)

    else:
        # Unknown interval type, default to 1 hour from now
        next_run = from_time + timedelta(hours=1)

    # `next_run` is a local wall clock time, so it's resolved against the timezone
    # to get the instant it refers to, which is what's stored and compared against.
    return next_run.replace(tzinfo=zone).astimezone(datetime_timezone.utc)
