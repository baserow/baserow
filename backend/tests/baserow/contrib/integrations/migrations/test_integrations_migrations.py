from datetime import datetime, timezone

from freezegun import freeze_time
import pytest


@pytest.mark.once_per_day_in_ci
@freeze_time("2026-02-15 10:30:00")
def test_0026_backfill_coreperiodicservice_next_run_at_forwards(
    migrator, teardown_table_metadata
):
    migrate_from = [
        ("integrations", "0025_coreperiodicservice_next_run_at"),
    ]
    migrate_to = [
        ("integrations", "0026_backfill_coreperiodicservice_next_run_at"),
    ]

    old_state = migrator.migrate(migrate_from)

    # Get models from old state
    CorePeriodicService = old_state.apps.get_model(
        "integrations", "CorePeriodicService"
    )
    Service = old_state.apps.get_model("core", "Service")
    ContentType = old_state.apps.get_model("contenttypes", "ContentType")

    # Create ContentType for CorePeriodicService
    service_content_type = ContentType.objects.get_for_model(Service)

    # Create test services with different intervals
    # All should have next_run_at=None before migration
    # Most have last_periodic_run (realistic scenario), one doesn't
    # Current time: 2026-02-15 10:30:00 (Sunday)
    services_data = [
        # Every 5 minutes
        # Sunday 15th, 10:30 now - DUE NOW (last ran 10:25, interval 5 min, next = 10:30)
        {
            "id": 1,
            "content_type": service_content_type,
            "interval": "MINUTE",
            "minute": 5,
            "last_periodic_run": datetime(2026, 2, 15, 10, 25, 0, tzinfo=timezone.utc),
            "expected_next_run": datetime(2026, 2, 15, 10, 30, 0, tzinfo=timezone.utc),
        },
        # Every hour at minute 45
        # Sunday 15th, 10:30 now - FUTURE RUN (last ran 09:45, next = 10:45)
        {
            "id": 2,
            "content_type": service_content_type,
            "interval": "HOUR",
            "minute": 45,
            "last_periodic_run": datetime(2026, 2, 15, 9, 45, 0, tzinfo=timezone.utc),
            "expected_next_run": datetime(2026, 2, 15, 10, 45, 0, tzinfo=timezone.utc),
        },
        # Every hour at minute 25
        # Sunday 15th, 10:30 now - OVERDUE (last ran 09:25, next = 10:25 - already passed)
        {
            "id": 3,
            "content_type": service_content_type,
            "interval": "HOUR",
            "minute": 25,
            "last_periodic_run": datetime(2026, 2, 15, 9, 25, 0, tzinfo=timezone.utc),
            "expected_next_run": datetime(2026, 2, 15, 10, 25, 0, tzinfo=timezone.utc),
        },
        # Every day at 14:30
        # Sunday 15th, 10:30 now - FUTURE RUN (last ran yesterday 14:30, next = today 14:30)
        {
            "id": 4,
            "content_type": service_content_type,
            "interval": "DAY",
            "minute": 30,
            "hour": 14,
            "last_periodic_run": datetime(2026, 2, 14, 14, 30, 0, tzinfo=timezone.utc),
            "expected_next_run": datetime(2026, 2, 15, 14, 30, 0, tzinfo=timezone.utc),
        },
        # Every day at 09:00
        # Sunday 15th, 10:30 now - OVERDUE (last ran yesterday 09:00, next = today 09:00 - already passed)
        {
            "id": 5,
            "content_type": service_content_type,
            "interval": "DAY",
            "minute": 0,
            "hour": 9,
            "last_periodic_run": datetime(2026, 2, 14, 9, 0, 0, tzinfo=timezone.utc),
            "expected_next_run": datetime(2026, 2, 15, 9, 0, 0, tzinfo=timezone.utc),
        },
        # Every Tuesday at 10:00
        # Sunday 15th, 10:30 now - Weekly (last ran Tues Feb 10th, next = this Tues Feb 17th)
        {
            "id": 6,
            "content_type": service_content_type,
            "interval": "WEEK",
            "minute": 0,
            "hour": 10,
            "day_of_week": 1,  # Tuesday
            "last_periodic_run": datetime(2026, 2, 10, 10, 0, 0, tzinfo=timezone.utc),
            "expected_next_run": datetime(2026, 2, 17, 10, 0, 0, tzinfo=timezone.utc),
        },
        # Every month on the 15th at 14:30
        # Sunday 15th, 10:30 now - Monthly (last ran Jan 15, next = today Feb 15 at 14:30)
        {
            "id": 7,
            "content_type": service_content_type,
            "interval": "MONTH",
            "minute": 30,
            "hour": 14,
            "day_of_month": 15,
            "last_periodic_run": datetime(2026, 1, 15, 14, 30, 0, tzinfo=timezone.utc),
            "expected_next_run": datetime(2026, 2, 15, 14, 30, 0, tzinfo=timezone.utc),
        },
        # Every month on the 10th at 09:00
        # Sunday 15th, 10:30 now - Monthly (last ran Feb 10, next = Mar 10)
        {
            "id": 8,
            "content_type": service_content_type,
            "interval": "MONTH",
            "minute": 0,
            "hour": 9,
            "day_of_month": 10,
            "last_periodic_run": datetime(2026, 2, 10, 9, 0, 0, tzinfo=timezone.utc),
            "expected_next_run": datetime(2026, 3, 10, 9, 0, 0, tzinfo=timezone.utc),
        },
        # Every 5 minutes
        # Sunday 15th, 10:30 now - Never run before (no last_periodic_run, calculates from now: 10:30 + 5 min = 10:35)
        {
            "id": 9,
            "content_type": service_content_type,
            "interval": "MINUTE",
            "minute": 5,
            "last_periodic_run": None,
            "expected_next_run": datetime(2026, 2, 15, 10, 35, 0, tzinfo=timezone.utc),
        },
    ]

    # Create the services (without next_run_at, which should be None)
    # Store expected values separately
    expected_values = {}
    for data in services_data:
        service_id = data["id"]
        expected_values[service_id] = {
            "next_run_at": data.pop("expected_next_run"),
            "interval": data["interval"],
        }
        CorePeriodicService.objects.create(**data)

    # Verify all services have next_run_at=None before migration
    assert CorePeriodicService.objects.filter(next_run_at__isnull=True).count() == 9

    # Run the migration
    new_state = migrator.migrate(migrate_to)
    NewCorePeriodicService = new_state.apps.get_model(
        "integrations", "CorePeriodicService"
    )

    # Verify all services now have next_run_at calculated
    assert NewCorePeriodicService.objects.filter(next_run_at__isnull=True).count() == 0

    # Verify each service has the correct next_run_at
    for service_id, expected_data in expected_values.items():
        service = NewCorePeriodicService.objects.get(id=service_id)
        expected_next_run = expected_data["next_run_at"]

        assert (
            service.next_run_at == expected_next_run
        ), f"Service {service_id} ({expected_data['interval']}): expected {expected_next_run}, got {service.next_run_at}"


@pytest.mark.once_per_day_in_ci
def test_0032_coreperiodicservice_timezone_defaults_existing_rows_to_utc(
    migrator, teardown_table_metadata
):
    """
    The schedule fields of services created before the schedule became timezone
    aware were already converted to UTC by the frontend. Defaulting them to UTC
    means they keep resolving to exactly the same instants, so deploying this
    doesn't quietly move anybody's live schedule.
    """

    migrate_from = [("integrations", "0031_corestartworkflowservice")]
    migrate_to = [("integrations", "0032_coreperiodicservice_timezone")]

    old_state = migrator.migrate(migrate_from)

    CorePeriodicService = old_state.apps.get_model(
        "integrations", "CorePeriodicService"
    )
    Service = old_state.apps.get_model("core", "Service")
    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    service_content_type = ContentType.objects.get_for_model(Service)

    # A weekly schedule which predates the timezone field entirely.
    CorePeriodicService.objects.create(
        id=1,
        content_type=service_content_type,
        interval="WEEK",
        day_of_week=0,
        hour=5,
        minute=0,
        next_run_at=datetime(2026, 2, 16, 5, 0, 0, tzinfo=timezone.utc),
    )

    new_state = migrator.migrate(migrate_to)
    CorePeriodicService = new_state.apps.get_model(
        "integrations", "CorePeriodicService"
    )

    service = CorePeriodicService.objects.get(id=1)
    assert service.timezone == "UTC"
    # The schedule itself is untouched by the migration.
    assert service.interval == "WEEK"
    assert (service.day_of_week, service.hour, service.minute) == (0, 5, 0)
    assert service.next_run_at == datetime(2026, 2, 16, 5, 0, 0, tzinfo=timezone.utc)
