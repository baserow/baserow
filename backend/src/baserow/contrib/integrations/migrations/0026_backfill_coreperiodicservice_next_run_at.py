from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.db import migrations
from django.utils import timezone


def _calculate_next_run(interval, minute, hour, day_of_week, day_of_month, from_time):
    """
    Calculate the next scheduled run time based on the service's schedule configuration.
    This is a copy of CorePeriodicServiceType.calculate_next_run() for use in the migration.
    """

    # Truncate to minute precision
    from_time = from_time.replace(second=0, microsecond=0)

    if interval == "MINUTE":
        # For minute intervals, add the interval to the from_time
        interval_minutes = minute if minute > 0 else 1
        next_run = from_time + timedelta(minutes=interval_minutes)

    elif interval == "HOUR":
        # Run at the specified minute of each hour
        next_run = from_time.replace(minute=minute)
        # If we've already passed this minute in the current hour, move to next hour
        if next_run <= from_time:
            next_run += timedelta(hours=1)

    elif interval == "DAY":
        # Run at the specified hour:minute each day
        next_run = from_time.replace(hour=hour, minute=minute)
        # If we've already passed this time today, move to tomorrow
        if next_run <= from_time:
            next_run += timedelta(days=1)

    elif interval == "WEEK":
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

    elif interval == "MONTH":
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


def forward(apps, schema_editor):
    """
    Backfill next_run_at for all existing CorePeriodicService records.
    """
    CorePeriodicService = apps.get_model("integrations", "CorePeriodicService")
    now = timezone.now().replace(second=0, microsecond=0)

    services_to_update = []

    # Only migrate services which have run, this will help reduce the
    # size of the queryset by excluding 'draft' workflows.
    services_which_have_run = CorePeriodicService.objects.exclude(
        last_periodic_run__isnull=True
    )
    for service in services_which_have_run:
        # Calculate next_run_at based on the service's schedule
        # Use last_periodic_run as the base if available, otherwise use now
        from_time = service.last_periodic_run if service.last_periodic_run else now

        next_run = _calculate_next_run(
            interval=service.interval,
            minute=service.minute,
            hour=service.hour,
            day_of_week=service.day_of_week,
            day_of_month=service.day_of_month,
            from_time=from_time,
        )

        # If the service has never run (no last_periodic_run), and the calculated
        # next_run is in the past, keep advancing until we get a future time.
        # For services that have run before, keep the calculated next_run even if
        # it's in the past, as they may be overdue and should run ASAP.
        if not service.last_periodic_run:
            while next_run < now:
                next_run = _calculate_next_run(
                    interval=service.interval,
                    minute=service.minute,
                    hour=service.hour,
                    day_of_week=service.day_of_week,
                    day_of_month=service.day_of_month,
                    from_time=next_run,
                )

        service.next_run_at = next_run
        services_to_update.append(service)

    # Bulk update all services
    if services_to_update:
        CorePeriodicService.objects.bulk_update(services_to_update, ["next_run_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0025_coreperiodicservice_next_run_at"),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
