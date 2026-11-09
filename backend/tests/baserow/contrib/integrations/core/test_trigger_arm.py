from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from freezegun import freeze_time

from baserow.contrib.integrations.core.constants import PERIODIC_INTERVAL_WEEK
from baserow.contrib.integrations.core.service_types import (
    CoreHTTPTriggerServiceType,
    CoreInboundEmailTriggerServiceType,
    CoreManualTriggerServiceType,
    CorePeriodicTriggerServiceType,
)
from baserow.core.registries import ImportExportConfig
from baserow.test_utils.pytest_conftest import fake_import_formula

WEEKLY_MONDAY_AT_FIVE = {
    "interval": PERIODIC_INTERVAL_WEEK,
    "day_of_week": 0,
    "hour": 5,
    "minute": 0,
}

WEBHOOK_TRIGGER_TYPES = [
    pytest.param(
        CoreHTTPTriggerServiceType, "create_core_http_trigger_service", id="http"
    ),
    pytest.param(
        CoreInboundEmailTriggerServiceType,
        "create_core_inbound_email_trigger_service",
        id="email",
    ),
]

PUBLISHABLE_TRIGGER_TYPES = [
    pytest.param(
        CorePeriodicTriggerServiceType, "create_core_periodic_service", id="periodic"
    ),
    *WEBHOOK_TRIGGER_TYPES,
]


@pytest.mark.django_db
def test_arm_is_a_no_op_by_default(data_fixture, django_assert_num_queries):
    service = data_fixture.create_core_manual_trigger_service()

    with django_assert_num_queries(0):
        CoreManualTriggerServiceType().arm(service)


@pytest.mark.django_db
def test_periodic_arm_schedules_the_next_run_from_now(data_fixture):
    service = data_fixture.create_core_periodic_service(
        **WEEKLY_MONDAY_AT_FIVE,
        next_run_at=datetime(2025, 2, 10, 5, 0, tzinfo=timezone.utc),
    )

    # A Wednesday: the stale Monday above must be replaced, not reused.
    with freeze_time("2025-02-12 14:23:00"):
        CorePeriodicTriggerServiceType().arm(service)

    service.refresh_from_db()
    assert service.next_run_at == datetime(2025, 2, 17, 5, 0, tzinfo=timezone.utc)


@pytest.mark.django_db
def test_periodic_arm_without_an_interval_does_nothing(
    data_fixture, django_assert_num_queries
):
    service = data_fixture.create_core_periodic_service(interval=None)

    with django_assert_num_queries(0):
        CorePeriodicTriggerServiceType().arm(service)

    service.refresh_from_db()
    assert service.next_run_at is None


@pytest.mark.django_db
@pytest.mark.parametrize("service_type_class,create_service", WEBHOOK_TRIGGER_TYPES)
def test_arm_makes_webhook_triggers_public(
    data_fixture, service_type_class, create_service
):
    service = getattr(data_fixture, create_service)(is_public=False)

    service_type_class().arm(service)

    service.refresh_from_db()
    assert service.is_public is True


@pytest.mark.django_db
@pytest.mark.parametrize("service_type_class,create_service", PUBLISHABLE_TRIGGER_TYPES)
@pytest.mark.parametrize("is_publishing", [True, False])
def test_import_arms_the_copy_only_when_publishing(
    data_fixture, service_type_class, create_service, is_publishing
):
    service_type = service_type_class()
    service = getattr(data_fixture, create_service)()
    serialized = service_type.export_serialized(service)

    with patch.object(service_type_class, "arm") as arm:
        imported = service_type.import_serialized(
            None,
            serialized,
            {},
            import_export_config=ImportExportConfig(
                include_permission_data=True, is_publishing=is_publishing
            ),
            import_formula=fake_import_formula,
        )

    if is_publishing:
        arm.assert_called_once_with(imported)
    else:
        arm.assert_not_called()
