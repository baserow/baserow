from datetime import datetime, timezone

from baserow.contrib.integrations.core.constants import (
    PERIODIC_INTERVAL_DAY,
    PERIODIC_INTERVAL_HOUR,
    PERIODIC_INTERVAL_MINUTE,
    PERIODIC_INTERVAL_MONTH,
    PERIODIC_INTERVAL_WEEK,
)

CALL_PERIODIC_SERVICES_THAT_ARE_DUE_CASES = [
    # Minute
    # Service due exactly now, should trigger
    (
        {
            "interval": PERIODIC_INTERVAL_MINUTE,
            "last_periodic_run": None,
            "next_run_at": datetime(2025, 2, 15, 10, 30, 0, tzinfo=timezone.utc),
        },
        "2025-02-15 10:30:45",
        True,
    ),
    # Service not yet due (1 minute from now)
    (
        {
            "interval": PERIODIC_INTERVAL_MINUTE,
            "last_periodic_run": datetime(2025, 2, 15, 10, 30, 30, tzinfo=timezone.utc),
            "next_run_at": datetime(2025, 2, 15, 10, 31, 0, tzinfo=timezone.utc),
        },
        "2025-02-15 10:30:45",
        False,
    ),
    # Service not yet due (next minute)
    (
        {
            "interval": PERIODIC_INTERVAL_MINUTE,
            "last_periodic_run": datetime(2025, 2, 15, 10, 30, 0, tzinfo=timezone.utc),
            "next_run_at": datetime(2025, 2, 15, 10, 31, 0, tzinfo=timezone.utc),
        },
        "2025-02-15 10:30:45",
        False,
    ),
    # Service overdue from previous minute
    (
        {
            "interval": PERIODIC_INTERVAL_MINUTE,
            "last_periodic_run": datetime(2025, 2, 15, 10, 28, 59, tzinfo=timezone.utc),
            "next_run_at": datetime(2025, 2, 15, 10, 29, 0, tzinfo=timezone.utc),
        },
        "2025-02-15 10:30:45",
        True,
    ),
    # Service heavily overdue (month old)
    (
        {
            "interval": PERIODIC_INTERVAL_MINUTE,
            "last_periodic_run": datetime(2025, 1, 16, 2, 59, 59, tzinfo=timezone.utc),
            "next_run_at": datetime(2025, 1, 16, 3, 0, 0, tzinfo=timezone.utc),
        },
        "2025-02-15 10:30:45",
        True,
    ),
    # 5-minute interval not yet due
    (
        {
            "minute": 5,
            "interval": PERIODIC_INTERVAL_MINUTE,
            "last_periodic_run": datetime(2025, 11, 6, 12, 0, 0, tzinfo=timezone.utc),
            "next_run_at": datetime(2025, 11, 6, 12, 5, 0, tzinfo=timezone.utc),
        },
        "2025-11-06 12:03:00",
        False,
    ),
    # 5-minute interval due exactly now
    (
        {
            "minute": 5,
            "interval": PERIODIC_INTERVAL_MINUTE,
            "last_periodic_run": datetime(2025, 11, 6, 12, 0, 0, tzinfo=timezone.utc),
            "next_run_at": datetime(2025, 11, 6, 12, 5, 0, tzinfo=timezone.utc),
        },
        "2025-11-06 12:05:00",
        True,
    ),
    # Hour
    # Hourly service due later this hour
    (
        {
            "interval": PERIODIC_INTERVAL_HOUR,
            "last_periodic_run": None,
            "minute": 34,
            "next_run_at": datetime(2025, 2, 15, 10, 34, 0, tzinfo=timezone.utc),
        },
        "2025-02-15 10:30:45",
        False,
    ),
    # Hourly service due next hour (already passed this hour)
    (
        {
            "interval": PERIODIC_INTERVAL_HOUR,
            "last_periodic_run": None,
            "minute": 34,
            "next_run_at": datetime(2025, 2, 15, 11, 34, 0, tzinfo=timezone.utc),
        },
        "2025-02-15 10:35:45",
        False,
    ),
    # Hourly service not yet due (next hour)
    (
        {
            "interval": PERIODIC_INTERVAL_HOUR,
            "last_periodic_run": datetime(2025, 2, 15, 10, 5, 45, tzinfo=timezone.utc),
            "minute": 5,
            "next_run_at": datetime(2025, 2, 15, 11, 5, 0, tzinfo=timezone.utc),
        },
        "2025-02-15 10:30:45",
        False,
    ),
    # Hourly service not yet due (later this hour)
    (
        {
            "interval": PERIODIC_INTERVAL_HOUR,
            "last_periodic_run": datetime(2025, 2, 15, 9, 45, 45, tzinfo=timezone.utc),
            "minute": 45,
            "next_run_at": datetime(2025, 2, 15, 10, 45, 0, tzinfo=timezone.utc),
        },
        "2025-02-15 10:30:45",
        False,
    ),
    # Hourly service overdue from previous hour
    (
        {
            "interval": PERIODIC_INTERVAL_HOUR,
            "last_periodic_run": datetime(2025, 2, 15, 9, 27, 45, tzinfo=timezone.utc),
            "minute": 31,
            "next_run_at": datetime(2025, 2, 15, 9, 31, 0, tzinfo=timezone.utc),
        },
        "2025-02-15 10:30:45",
        True,
    ),
    # Hourly service overdue from previous hour
    (
        {
            "interval": PERIODIC_INTERVAL_HOUR,
            "last_periodic_run": datetime(2025, 2, 15, 9, 27, 45, tzinfo=timezone.utc),
            "minute": 29,
            "next_run_at": datetime(2025, 2, 15, 9, 29, 0, tzinfo=timezone.utc),
        },
        "2025-02-15 10:30:45",
        True,
    ),
    # Day
    # Daily service due later today
    (
        {
            "interval": PERIODIC_INTERVAL_DAY,
            "last_periodic_run": None,
            "minute": 34,
            "hour": 10,
            "next_run_at": datetime(2025, 2, 15, 10, 34, 0, tzinfo=timezone.utc),
        },
        "2025-02-15 10:30:45",
        False,
    ),
    # Daily service due tomorrow (passed today's time)
    (
        {
            "interval": PERIODIC_INTERVAL_DAY,
            "last_periodic_run": None,
            "minute": 34,
            "hour": 10,
            "next_run_at": datetime(2025, 2, 16, 10, 34, 0, tzinfo=timezone.utc),
        },
        "2025-02-15 10:35:45",
        False,
    ),
    # Service overdue from previous day
    (
        {
            "interval": PERIODIC_INTERVAL_HOUR,
            "last_periodic_run": datetime(2025, 2, 14, 10, 40, 45, tzinfo=timezone.utc),
            "minute": 34,
            "hour": 10,
            "next_run_at": datetime(2025, 2, 14, 11, 34, 0, tzinfo=timezone.utc),
        },
        "2025-02-15 10:30:45",
        True,
    ),
    # Service overdue from previous day
    (
        {
            "interval": PERIODIC_INTERVAL_HOUR,
            "last_periodic_run": datetime(2025, 2, 14, 9, 45, 45, tzinfo=timezone.utc),
            "minute": 45,
            "hour": 11,
            "next_run_at": datetime(2025, 2, 14, 10, 45, 0, tzinfo=timezone.utc),
        },
        "2025-02-15 10:30:45",
        True,
    ),
    # Service overdue from previous day
    (
        {
            "interval": PERIODIC_INTERVAL_HOUR,
            "last_periodic_run": datetime(2025, 2, 14, 9, 45, 45, tzinfo=timezone.utc),
            "minute": 15,
            "hour": 10,
            "next_run_at": datetime(2025, 2, 14, 10, 15, 0, tzinfo=timezone.utc),
        },
        "2025-02-15 10:30:45",
        True,
    ),
    # Week
    # Weekly service due tomorrow
    (
        {
            "interval": PERIODIC_INTERVAL_WEEK,
            "last_periodic_run": None,
            "minute": 34,
            "hour": 10,
            "day_of_week": 1,  # Tuesday
            "next_run_at": datetime(2025, 2, 11, 10, 34, 0, tzinfo=timezone.utc),
        },
        "2025-02-10 10:30:45",
        False,
    ),
    # Weekly service due next week (passed this week's time)
    (
        {
            "interval": PERIODIC_INTERVAL_WEEK,
            "last_periodic_run": None,
            "minute": 34,
            "hour": 10,
            "day_of_week": 1,  # Tuesday
            "next_run_at": datetime(2025, 2, 18, 10, 34, 0, tzinfo=timezone.utc),
        },
        "2025-02-11 10:35:45",
        False,
    ),
    # Service overdue from previous week
    (
        {
            "interval": PERIODIC_INTERVAL_HOUR,
            "last_periodic_run": datetime(2025, 2, 4, 10, 40, 45, tzinfo=timezone.utc),
            "minute": 34,
            "hour": 10,
            "day_of_week": 1,  # Tuesday
            "next_run_at": datetime(2025, 2, 4, 11, 34, 0, tzinfo=timezone.utc),
        },
        "2025-02-11 10:30:45",
        True,
    ),
    # Service overdue from previous week
    (
        {
            "interval": PERIODIC_INTERVAL_HOUR,
            "last_periodic_run": datetime(2025, 2, 4, 9, 45, 45, tzinfo=timezone.utc),
            "minute": 45,
            "hour": 11,
            "day_of_week": 1,  # Tuesday
            "next_run_at": datetime(2025, 2, 4, 10, 45, 0, tzinfo=timezone.utc),
        },
        "2025-02-11 10:30:45",
        True,
    ),
    # Service overdue from previous week (by more than an hour)
    (
        {
            "interval": PERIODIC_INTERVAL_HOUR,
            "last_periodic_run": datetime(2025, 2, 4, 9, 45, 45, tzinfo=timezone.utc),
            "minute": 45,
            "hour": 11,
            "day_of_week": 1,  # Tuesday
            "next_run_at": datetime(2025, 2, 4, 10, 45, 0, tzinfo=timezone.utc),
        },
        "2025-02-11 11:46:45",
        True,
    ),
    # Month
    # Monthly service due in 2 days
    (
        {
            "interval": PERIODIC_INTERVAL_MONTH,
            "last_periodic_run": None,
            "minute": 34,
            "hour": 10,
            "day_of_month": 12,
            "next_run_at": datetime(2025, 2, 12, 10, 34, 0, tzinfo=timezone.utc),
        },
        "2025-02-10 10:30:45",
        False,
    ),
    # Monthly service due next month (passed this month's time)
    (
        {
            "interval": PERIODIC_INTERVAL_MONTH,
            "last_periodic_run": None,
            "minute": 34,
            "hour": 10,
            "day_of_month": 11,
            "next_run_at": datetime(2025, 3, 11, 10, 34, 0, tzinfo=timezone.utc),
        },
        "2025-02-11 10:35:45",
        False,
    ),
    # Service overdue from previous month
    (
        {
            "interval": PERIODIC_INTERVAL_MONTH,
            "last_periodic_run": datetime(2025, 1, 10, 10, 40, 45, tzinfo=timezone.utc),
            "minute": 34,
            "hour": 10,
            "day_of_month": 11,
            "next_run_at": datetime(2025, 1, 11, 10, 34, 0, tzinfo=timezone.utc),
        },
        "2025-02-11 10:30:45",
        True,
    ),
    # Service overdue from previous month
    (
        {
            "interval": PERIODIC_INTERVAL_MONTH,
            "last_periodic_run": datetime(2025, 1, 11, 10, 20, 45, tzinfo=timezone.utc),
            "minute": 45,
            "hour": 11,
            "day_of_month": 11,
            "next_run_at": datetime(2025, 1, 11, 11, 45, 0, tzinfo=timezone.utc),
        },
        "2025-02-11 10:30:45",
        True,
    ),
    # Service overdue from previous month (by more than an hour)
    (
        {
            "interval": PERIODIC_INTERVAL_MONTH,
            "last_periodic_run": datetime(2025, 1, 11, 11, 44, 45, tzinfo=timezone.utc),
            "minute": 45,
            "hour": 11,
            "day_of_month": 11,
            "next_run_at": datetime(2025, 1, 11, 11, 45, 0, tzinfo=timezone.utc),
        },
        "2025-02-11 11:46:45",
        True,
    ),
]

PERIODIC_SERVICE_CALCULATE_NEXT_RUN_CASES = [
    # MINUTE interval tests
    (
        PERIODIC_INTERVAL_MINUTE,
        5,  # Every 5 minutes
        0,
        0,
        1,
        datetime(2025, 2, 15, 10, 30, 0, tzinfo=timezone.utc),
        datetime(2025, 2, 15, 10, 35, 0, tzinfo=timezone.utc),
    ),
    (
        PERIODIC_INTERVAL_MINUTE,
        1,  # Every minute
        0,
        0,
        1,
        datetime(2025, 2, 15, 10, 30, 0, tzinfo=timezone.utc),
        datetime(2025, 2, 15, 10, 31, 0, tzinfo=timezone.utc),
    ),
    (
        PERIODIC_INTERVAL_MINUTE,
        15,  # Every 15 minutes
        0,
        0,
        1,
        datetime(2025, 2, 15, 10, 45, 0, tzinfo=timezone.utc),
        datetime(2025, 2, 15, 11, 0, 0, tzinfo=timezone.utc),
    ),
    # HOUR interval tests
    (
        PERIODIC_INTERVAL_HOUR,
        25,  # At minute 25 of each hour
        0,
        0,
        1,
        datetime(2025, 2, 15, 10, 20, 0, tzinfo=timezone.utc),
        datetime(2025, 2, 15, 10, 25, 0, tzinfo=timezone.utc),
    ),
    (
        PERIODIC_INTERVAL_HOUR,
        25,
        0,
        0,
        1,
        datetime(2025, 2, 15, 10, 30, 0, tzinfo=timezone.utc),
        datetime(
            2025, 2, 15, 11, 25, 0, tzinfo=timezone.utc
        ),  # Already passed, next hour
    ),
    (
        PERIODIC_INTERVAL_HOUR,
        0,  # On the hour
        0,
        0,
        1,
        datetime(2025, 2, 15, 10, 30, 0, tzinfo=timezone.utc),
        datetime(2025, 2, 15, 11, 0, 0, tzinfo=timezone.utc),
    ),
    # DAY interval tests
    (
        PERIODIC_INTERVAL_DAY,
        30,  # minute
        14,  # hour (14:30)
        0,
        1,
        datetime(2025, 2, 15, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2025, 2, 15, 14, 30, 0, tzinfo=timezone.utc),  # Today at 14:30
    ),
    (
        PERIODIC_INTERVAL_DAY,
        30,
        14,
        0,
        1,
        datetime(2025, 2, 15, 15, 0, 0, tzinfo=timezone.utc),
        datetime(2025, 2, 16, 14, 30, 0, tzinfo=timezone.utc),  # Tomorrow at 14:30
    ),
    (
        PERIODIC_INTERVAL_DAY,
        0,
        0,  # Midnight
        0,
        1,
        datetime(2025, 2, 15, 23, 30, 0, tzinfo=timezone.utc),
        datetime(2025, 2, 16, 0, 0, 0, tzinfo=timezone.utc),
    ),
    # WEEK interval tests
    (
        PERIODIC_INTERVAL_WEEK,
        30,  # minute
        14,  # hour
        1,  # Tuesday
        1,
        datetime(2025, 2, 10, 10, 0, 0, tzinfo=timezone.utc),  # Monday
        datetime(2025, 2, 11, 14, 30, 0, tzinfo=timezone.utc),  # Next Tuesday
    ),
    (
        PERIODIC_INTERVAL_WEEK,
        30,
        14,
        1,  # Tuesday
        1,
        datetime(2025, 2, 11, 10, 0, 0, tzinfo=timezone.utc),  # Tuesday morning
        datetime(2025, 2, 11, 14, 30, 0, tzinfo=timezone.utc),  # Same Tuesday afternoon
    ),
    (
        PERIODIC_INTERVAL_WEEK,
        30,
        14,
        1,  # Tuesday
        1,
        datetime(2025, 2, 11, 15, 0, 0, tzinfo=timezone.utc),  # Tuesday after 14:30
        datetime(2025, 2, 18, 14, 30, 0, tzinfo=timezone.utc),  # Next Tuesday
    ),
    (
        PERIODIC_INTERVAL_WEEK,
        30,
        14,
        0,  # Monday
        1,
        datetime(2025, 2, 15, 10, 0, 0, tzinfo=timezone.utc),  # Saturday
        datetime(2025, 2, 17, 14, 30, 0, tzinfo=timezone.utc),  # Next Monday
    ),
    # MONTH interval tests
    (
        PERIODIC_INTERVAL_MONTH,
        30,  # minute
        14,  # hour
        0,
        15,  # day 15
        datetime(2025, 2, 10, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2025, 2, 15, 14, 30, 0, tzinfo=timezone.utc),  # This month on 15th
    ),
    (
        PERIODIC_INTERVAL_MONTH,
        30,
        14,
        0,
        15,
        datetime(2025, 2, 15, 15, 0, 0, tzinfo=timezone.utc),  # After 14:30 on 15th
        datetime(2025, 3, 15, 14, 30, 0, tzinfo=timezone.utc),  # Next month on 15th
    ),
    (
        PERIODIC_INTERVAL_MONTH,
        30,
        14,
        0,
        31,  # Day that doesn't exist in all months
        datetime(2025, 1, 31, 15, 0, 0, tzinfo=timezone.utc),  # Jan 31st
        datetime(
            2025, 2, 28, 14, 30, 0, tzinfo=timezone.utc
        ),  # Last day of Feb (non-leap)
    ),
    (
        PERIODIC_INTERVAL_MONTH,
        0,
        0,
        0,
        1,  # First of month at midnight
        datetime(2025, 2, 15, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2025, 3, 1, 0, 0, 0, tzinfo=timezone.utc),
    ),
    # Day doesn't exist in current month (e.g., Feb 30th)
    (
        PERIODIC_INTERVAL_MONTH,
        30,
        14,
        0,
        30,  # Day 30 doesn't exist in February
        datetime(2025, 2, 10, 10, 0, 0, tzinfo=timezone.utc),  # Currently Feb 10th
        datetime(2025, 2, 28, 14, 30, 0, tzinfo=timezone.utc),  # Falls back to Feb 28th
    ),
    # Day doesn't exist in current month and time has passed (move to next month)
    (
        PERIODIC_INTERVAL_MONTH,
        30,
        14,
        0,
        30,  # Day 30 doesn't exist in February
        datetime(2025, 2, 28, 15, 0, 0, tzinfo=timezone.utc),  # After 14:30 on Feb 28th
        datetime(2025, 3, 30, 14, 30, 0, tzinfo=timezone.utc),  # March 30th exists
    ),
    # Day doesn't exist in current or next month (Feb -> Mar with day 31)
    (
        PERIODIC_INTERVAL_MONTH,
        30,
        14,
        0,
        31,  # Day 31
        datetime(2025, 2, 10, 10, 0, 0, tzinfo=timezone.utc),  # Currently Feb 10th
        datetime(2025, 2, 28, 14, 30, 0, tzinfo=timezone.utc),  # Falls back to Feb 28th
    ),
]

PERIODIC_SERVICE_NEXT_RUN_SET_CASES = [
    # MINUTE - every 5 minutes
    (
        {"interval": PERIODIC_INTERVAL_MINUTE, "minute": 5},
        "2025-02-15 10:30:00",
        datetime(2025, 2, 15, 10, 35, 0, tzinfo=timezone.utc),
    ),
    # HOUR - every hour at minute 25
    (
        {"interval": PERIODIC_INTERVAL_HOUR, "minute": 25},
        "2025-02-15 10:20:00",
        datetime(2025, 2, 15, 10, 25, 0, tzinfo=timezone.utc),
    ),
    (
        {"interval": PERIODIC_INTERVAL_HOUR, "minute": 25},
        "2025-02-15 10:30:00",
        datetime(
            2025, 2, 15, 11, 25, 0, tzinfo=timezone.utc
        ),  # Past 10:25, so next hour
    ),
    # DAY - every day at 14:30
    (
        {"interval": PERIODIC_INTERVAL_DAY, "minute": 30, "hour": 14},
        "2025-02-15 10:00:00",
        datetime(2025, 2, 15, 14, 30, 0, tzinfo=timezone.utc),
    ),
    (
        {"interval": PERIODIC_INTERVAL_DAY, "minute": 30, "hour": 14},
        "2025-02-15 15:00:00",
        datetime(2025, 2, 16, 14, 30, 0, tzinfo=timezone.utc),  # Tomorrow
    ),
    # WEEK - every Tuesday at 14:30
    (
        {
            "interval": PERIODIC_INTERVAL_WEEK,
            "minute": 30,
            "hour": 14,
            "day_of_week": 1,  # Tuesday
        },
        "2025-02-10 10:00:00",  # Monday
        datetime(2025, 2, 11, 14, 30, 0, tzinfo=timezone.utc),  # Tuesday
    ),
    # MONTH - 15th of each month at 14:30
    (
        {
            "interval": PERIODIC_INTERVAL_MONTH,
            "minute": 30,
            "hour": 14,
            "day_of_month": 15,
        },
        "2025-02-10 10:00:00",
        datetime(2025, 2, 15, 14, 30, 0, tzinfo=timezone.utc),
    ),
]
