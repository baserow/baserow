from datetime import datetime, timedelta
from typing import Optional

from django.utils import timezone

from dateutil.relativedelta import relativedelta

from baserow.contrib.integrations.core.constants import (
    PERIODIC_INTERVAL_DAY,
    PERIODIC_INTERVAL_HOUR,
    PERIODIC_INTERVAL_MINUTE,
    PERIODIC_INTERVAL_MONTH,
    PERIODIC_INTERVAL_WEEK,
)


def calculate_next_periodic_run(
    interval: str,
    minute: int,
    hour: int,
    day_of_week: int,
    day_of_month: int,
    from_time: Optional[datetime] = None,
) -> datetime:
    """
    Calculate the next scheduled run time based on the service's schedule configuration.

    :param interval: The interval type (MINUTE, HOUR, DAY, WEEK, MONTH)
    :param minute: The minute value (0-59)
    :param hour: The hour value (0-23)
    :param day_of_week: The day of week (0=Monday, 6=Sunday)
    :param day_of_month: The day of month (1-31)
    :param from_time: Calculate next run from this time (defaults to now)
    :return: The next scheduled run time
    """

    if from_time is None:
        from_time = timezone.now()

    # Truncate to minute precision
    from_time = from_time.replace(second=0, microsecond=0)

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

    return next_run
