from datetime import datetime, time, timezone
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone as django_timezone

import pytest
import responses
from baserow_premium.license.exceptions import FeaturesNotAvailableError
from freezegun.api import freeze_time

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.models import DataSync
from baserow.core.db import specific_iterator
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.notifications.models import Notification
from baserow_enterprise.data_sync.handler import EnterpriseDataSyncHandler
from baserow_enterprise.data_sync.models import (
    DATA_SYNC_INTERVAL_DAILY,
    DATA_SYNC_INTERVAL_MANUAL,
    DEACTIVATION_REASON_FAILURE,
    DEACTIVATION_REASON_LICENSE_UNAVAILABLE,
    PeriodicDataSyncInterval,
)
from baserow_enterprise.data_sync.notification_types import (
    PeriodicDataSyncDeactivatedNotificationType,
)


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_update_periodic_data_sync_interval_licence_check(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    data_sync = enterprise_data_fixture.create_ical_data_sync(user=user)

    with pytest.raises(FeaturesNotAvailableError):
        EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
            user=user,
            data_sync=data_sync,
            interval="MANUAL",
            when=time(hour=12, minute=10),
        )


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_update_periodic_data_sync_interval_check_permissions(
    enterprise_data_fixture, synced_roles
):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    data_sync = enterprise_data_fixture.create_ical_data_sync()

    with pytest.raises(UserNotInWorkspace):
        EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
            user=user,
            data_sync=data_sync,
            interval="MANUAL",
            when=time(hour=12, minute=10),
        )


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_update_periodic_data_sync_interval_create(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    data_sync = enterprise_data_fixture.create_ical_data_sync(user=user)

    periodic_data_sync_interval = (
        EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
            user=user,
            data_sync=data_sync,
            interval="DAILY",
            when=time(hour=12, minute=10, second=1, microsecond=1),
        )
    )

    fetched_periodic_data_sync_interval = PeriodicDataSyncInterval.objects.all().first()
    assert periodic_data_sync_interval.id == fetched_periodic_data_sync_interval.id
    assert (
        periodic_data_sync_interval.data_sync_id
        == periodic_data_sync_interval.data_sync_id
        == data_sync.id
    )
    assert (
        periodic_data_sync_interval.interval
        == periodic_data_sync_interval.interval
        == "DAILY"
    )
    assert (
        periodic_data_sync_interval.when
        == periodic_data_sync_interval.when
        == time(hour=12, minute=10, second=1, microsecond=1)
    )
    assert periodic_data_sync_interval.authorized_user_id == user.id
    assert periodic_data_sync_interval.automatically_deactivated is False


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_update_periodic_data_sync_interval_update(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    data_sync = enterprise_data_fixture.create_ical_data_sync(user=user)

    EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=data_sync,
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )

    periodic_data_sync_interval = (
        EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
            user=user,
            data_sync=data_sync,
            interval="HOURLY",
            when=time(hour=14, minute=12, second=1, microsecond=1),
        )
    )

    fetched_periodic_data_sync_interval = PeriodicDataSyncInterval.objects.all().first()
    assert periodic_data_sync_interval.id == fetched_periodic_data_sync_interval.id
    assert (
        periodic_data_sync_interval.data_sync_id
        == periodic_data_sync_interval.data_sync_id
        == data_sync.id
    )
    assert (
        periodic_data_sync_interval.interval
        == periodic_data_sync_interval.interval
        == "HOURLY"
    )
    assert (
        periodic_data_sync_interval.when
        == periodic_data_sync_interval.when
        == time(hour=14, minute=12, second=1, microsecond=1)
    )
    assert periodic_data_sync_interval.authorized_user_id == user.id
    assert periodic_data_sync_interval.automatically_deactivated is False


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_update_periodic_data_sync_interval_update_automatically_disabled(
    enterprise_data_fixture,
):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    data_sync = enterprise_data_fixture.create_ical_data_sync(user=user)

    periodic_data_sync = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=data_sync,
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )
    periodic_data_sync.automatically_deactivated = True
    periodic_data_sync.save()

    periodic_data_sync = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=data_sync,
        interval="HOURLY",
        when=time(hour=14, minute=12, second=1, microsecond=1),
    )
    assert periodic_data_sync.automatically_deactivated is False


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_call_daily_periodic_data_sync_syncs(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    not_yet_executed_1 = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )
    not_yet_executed_1.refresh_from_db()

    not_yet_executed_2 = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
        interval="DAILY",
        when=time(hour=12, minute=30, second=1, microsecond=1),
    )

    already_executed_today_1 = (
        EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
            user=user,
            data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
            interval="DAILY",
            when=time(hour=12, minute=10, second=1, microsecond=1),
        )
    )
    already_executed_today_1.last_periodic_sync = datetime(
        2024, 10, 10, 11, 0, 1, 1, tzinfo=timezone.utc
    )
    already_executed_today_1.save()

    already_executed_yesterday_1 = (
        EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
            user=user,
            data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
            interval="DAILY",
            when=time(hour=12, minute=10, second=1, microsecond=1),
        )
    )
    already_executed_yesterday_1.last_periodic_sync = datetime(
        2024, 10, 9, 11, 0, 1, 1, tzinfo=timezone.utc
    )
    already_executed_yesterday_1.save()

    with freeze_time("2024-10-10T12:15:00.00Z") as frozen:
        EnterpriseDataSyncHandler.call_periodic_data_sync_syncs_that_are_due()
        frozen_datetime = django_timezone.now()

    not_yet_executed_1.refresh_from_db()
    # executed because not yet executed before and due.
    assert not_yet_executed_1.last_periodic_sync == frozen_datetime

    not_yet_executed_2.refresh_from_db()
    # skipped because not yet due
    assert not_yet_executed_2.last_periodic_sync != frozen_datetime

    already_executed_today_1.refresh_from_db()
    # skipped because already executed
    assert already_executed_today_1.last_periodic_sync != frozen_datetime

    already_executed_yesterday_1.refresh_from_db()
    # executed because was last executed yesterday.
    assert already_executed_yesterday_1.last_periodic_sync == frozen_datetime

    with freeze_time("2024-10-10T12:31:00.00Z") as frozen:
        EnterpriseDataSyncHandler.call_periodic_data_sync_syncs_that_are_due()
        frozen_datetime = django_timezone.now()

    not_yet_executed_1.refresh_from_db()
    # not executed because not yet due.
    assert not_yet_executed_1.last_periodic_sync != frozen_datetime

    not_yet_executed_2.refresh_from_db()
    # executed because not yet executed before and due.
    assert not_yet_executed_2.last_periodic_sync == frozen_datetime

    already_executed_today_1.refresh_from_db()
    # not executed because not yet due.
    assert already_executed_today_1.last_periodic_sync != frozen_datetime

    already_executed_yesterday_1.refresh_from_db()
    # not executed because not yet due.
    assert already_executed_yesterday_1.last_periodic_sync != frozen_datetime


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_call_hourly_periodic_data_sync_syncs(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    not_yet_executed_1 = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
        interval="HOURLY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )
    not_yet_executed_1.refresh_from_db()

    not_yet_executed_2 = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
        interval="HOURLY",
        when=time(hour=12, minute=30, second=1, microsecond=1),
    )

    already_executed_this_hour_1 = (
        EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
            user=user,
            data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
            interval="HOURLY",
            when=time(hour=12, minute=10, second=1, microsecond=1),
        )
    )
    already_executed_this_hour_1.last_periodic_sync = datetime(
        2024, 10, 10, 12, 10, 1, 1, tzinfo=timezone.utc
    )
    already_executed_this_hour_1.save()

    already_executed_last_hour_1 = (
        EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
            user=user,
            data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
            interval="HOURLY",
            when=time(hour=12, minute=10, second=1, microsecond=1),
        )
    )
    already_executed_last_hour_1.last_periodic_sync = datetime(
        2024, 10, 10, 11, 20, 1, 1, tzinfo=timezone.utc
    )
    already_executed_last_hour_1.save()

    with freeze_time("2024-10-10T12:15:00.00Z") as frozen:
        EnterpriseDataSyncHandler.call_periodic_data_sync_syncs_that_are_due()
        frozen_datetime = django_timezone.now()

    not_yet_executed_1.refresh_from_db()
    # executed because not yet executed before and due.
    assert not_yet_executed_1.last_periodic_sync == frozen_datetime

    not_yet_executed_2.refresh_from_db()
    # skipped because not yet due
    assert not_yet_executed_2.last_periodic_sync != frozen_datetime

    already_executed_this_hour_1.refresh_from_db()
    # skipped because already executed
    assert already_executed_this_hour_1.last_periodic_sync != frozen_datetime

    already_executed_last_hour_1.refresh_from_db()
    # executed because was last executed yesterday.
    assert already_executed_last_hour_1.last_periodic_sync == frozen_datetime

    with freeze_time("2024-10-10T12:35:00.00Z") as frozen:
        EnterpriseDataSyncHandler.call_periodic_data_sync_syncs_that_are_due()
        frozen_datetime = django_timezone.now()

    not_yet_executed_1.refresh_from_db()
    # not executed because not yet due.
    assert not_yet_executed_1.last_periodic_sync != frozen_datetime

    not_yet_executed_2.refresh_from_db()
    # executed because not yet executed before and due.
    assert not_yet_executed_2.last_periodic_sync == frozen_datetime

    already_executed_this_hour_1.refresh_from_db()
    # not executed because not yet due.
    assert already_executed_this_hour_1.last_periodic_sync != frozen_datetime

    already_executed_last_hour_1.refresh_from_db()
    # not executed because not yet due.
    assert already_executed_last_hour_1.last_periodic_sync != frozen_datetime


@pytest.mark.django_db(transaction=True)
@pytest.mark.data_sync
@override_settings(DEBUG=True)
@patch("baserow_enterprise.data_sync.handler.sync_periodic_data_sync")
def test_call_periodic_data_sync_syncs_starts_task(
    mock_sync_periodic_data_sync,
    enterprise_data_fixture,
    synced_roles,
):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    not_yet_executed_1 = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )
    not_yet_executed_1.refresh_from_db()

    with freeze_time("2024-10-10T12:15:00.00Z"):
        with transaction.atomic():
            EnterpriseDataSyncHandler.call_periodic_data_sync_syncs_that_are_due()

    mock_sync_periodic_data_sync.delay.assert_called_once()
    args = mock_sync_periodic_data_sync.delay.call_args
    assert args[0][0] == not_yet_executed_1.id


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_skip_automatically_deactivated_periodic_data_syncs(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    not_yet_executed_1 = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )

    enterprise_data_fixture.delete_all_licenses()

    with freeze_time("2024-10-10T12:15:00.00Z"):
        with transaction.atomic():
            EnterpriseDataSyncHandler.call_periodic_data_sync_syncs_that_are_due()

    not_yet_executed_1.refresh_from_db()
    # Should not be triggered because there was no license.
    assert not_yet_executed_1.last_periodic_sync is None


@pytest.mark.django_db(transaction=True, databases=["default", "default-copy"])
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_skip_locked_data_syncs(enterprise_data_fixture, synced_roles):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    not_yet_executed_1 = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )
    not_yet_executed_2 = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )

    with transaction.atomic(using="default-copy"):
        PeriodicDataSyncInterval.objects.using("default-copy").filter(
            id=not_yet_executed_1.id
        ).select_for_update().get()
        DataSync.objects.using("default-copy").filter(
            id=not_yet_executed_2.data_sync_id
        ).select_for_update().get()

        with freeze_time("2024-10-10T12:15:00.00Z"):
            with transaction.atomic():
                EnterpriseDataSyncHandler.call_periodic_data_sync_syncs_that_are_due()

    not_yet_executed_1.refresh_from_db()
    # Should not be triggered because the periodic data sync object was locked.
    assert not_yet_executed_1.last_periodic_sync is None

    not_yet_executed_2.refresh_from_db()
    # Should not be triggered because there the data sync was locked.
    assert not_yet_executed_2.last_periodic_sync is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.data_sync
@override_settings(DEBUG=True)
@patch("baserow_enterprise.data_sync.handler.sync_periodic_data_sync")
def test_skip_syncing_data_syncs(
    mock_sync_periodic_data_sync, enterprise_data_fixture, synced_roles
):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    not_yet_executed_1 = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )

    lock_key = DataSyncHandler().get_table_sync_lock_key(
        not_yet_executed_1.data_sync_id
    )
    cache.add(lock_key, "locked", timeout=2)

    with freeze_time("2024-10-10T12:15:00.00Z"):
        with transaction.atomic():
            EnterpriseDataSyncHandler.call_periodic_data_sync_syncs_that_are_due()

    not_yet_executed_1.refresh_from_db()
    # Should be updated if the data sync is already running.
    assert not_yet_executed_1.last_periodic_sync is not None

    # Should not be called if the data sync is already running.
    mock_sync_periodic_data_sync.delay.assert_not_called()


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_sync_periodic_data_sync_deactivated(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    periodic_data_sync = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )
    periodic_data_sync.automatically_deactivated = True
    periodic_data_sync.save()

    assert (
        EnterpriseDataSyncHandler.sync_periodic_data_sync(periodic_data_sync.id)
        is False
    )

    periodic_data_sync.data_sync.refresh_from_db()
    assert periodic_data_sync.data_sync.last_sync is None


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_sync_periodic_data_sync_already_syncing(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    periodic_data_sync = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )

    lock_key = DataSyncHandler().get_table_sync_lock_key(
        periodic_data_sync.data_sync_id
    )
    cache.add(lock_key, "locked", timeout=2)

    assert (
        EnterpriseDataSyncHandler.sync_periodic_data_sync(periodic_data_sync.id)
        is False
    )

    periodic_data_sync.data_sync.refresh_from_db()
    assert periodic_data_sync.data_sync.last_sync is None


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
@responses.activate
def test_sync_periodic_data_sync_consecutive_failed_count_increases(
    enterprise_data_fixture,
):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=404,
        body="",
    )

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    periodic_data_sync = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )

    assert (
        EnterpriseDataSyncHandler.sync_periodic_data_sync(periodic_data_sync.id) is True
    )

    periodic_data_sync.refresh_from_db()
    assert periodic_data_sync.consecutive_failed_count == 1


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(
    DEBUG=True, BASEROW_ENTERPRISE_MAX_PERIODIC_DATA_SYNC_CONSECUTIVE_ERRORS=2
)
@responses.activate
def test_sync_periodic_data_sync_consecutive_failed_count_reset(
    enterprise_data_fixture,
):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body="""BEGIN:VCALENDAR
VERSION:2.0
END:VCALENDAR""",
    )

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    periodic_data_sync = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(
            user=user, ical_url="https://baserow.io/ical.ics"
        ),
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )
    periodic_data_sync.consecutive_failed_count = 1
    periodic_data_sync.save()

    assert (
        EnterpriseDataSyncHandler.sync_periodic_data_sync(periodic_data_sync.id) is True
    )

    periodic_data_sync.refresh_from_db()
    assert periodic_data_sync.consecutive_failed_count == 0


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
@responses.activate
def test_sync_periodic_data_sync_deactivated_max_failure(enterprise_data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=404,
        body="",
    )

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    periodic_data_sync = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )
    periodic_data_sync.consecutive_failed_count = 3
    periodic_data_sync.save()

    assert (
        EnterpriseDataSyncHandler.sync_periodic_data_sync(periodic_data_sync.id) is True
    )

    periodic_data_sync.refresh_from_db()
    assert periodic_data_sync.consecutive_failed_count == 4
    assert periodic_data_sync.automatically_deactivated is True


@pytest.mark.django_db(transaction=True)
@pytest.mark.data_sync
@override_settings(DEBUG=True)
@responses.activate
def test_sync_periodic_data_sync_deactivated_max_failure_notification_send(
    enterprise_data_fixture,
    synced_roles,
):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=404,
        body="",
    )

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    periodic_data_sync = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )
    periodic_data_sync.consecutive_failed_count = 3
    periodic_data_sync.save()

    with transaction.atomic():
        EnterpriseDataSyncHandler.sync_periodic_data_sync(periodic_data_sync.id)

    all_notifications = list(Notification.objects.all())
    assert len(all_notifications) == 1
    recipient_ids = [r.id for r in all_notifications[0].recipients.all()]
    assert recipient_ids == [user.id]
    assert all_notifications[0].type == PeriodicDataSyncDeactivatedNotificationType.type
    assert all_notifications[0].broadcast is False
    assert (
        all_notifications[0].workspace_id
        == periodic_data_sync.data_sync.table.database.workspace_id
    )
    assert all_notifications[0].sender is None
    assert all_notifications[0].data == {
        "data_sync_id": periodic_data_sync.data_sync_id,
        "table_name": periodic_data_sync.data_sync.table.name,
        "table_id": periodic_data_sync.data_sync.table.id,
        "database_id": periodic_data_sync.data_sync.table.database_id,
        "deactivation_reason": DEACTIVATION_REASON_FAILURE,
    }


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_sync_periodic_data_sync_authorized_user_is_none(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    periodic_data_sync = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )
    periodic_data_sync.authorized_user is None
    periodic_data_sync.save()

    assert (
        EnterpriseDataSyncHandler.sync_periodic_data_sync(periodic_data_sync.id) is True
    )

    periodic_data_sync.refresh_from_db()
    assert periodic_data_sync.consecutive_failed_count == 1


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
@responses.activate
def test_sync_periodic_data_sync(enterprise_data_fixture):
    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        status=200,
        body="""BEGIN:VCALENDAR
VERSION:2.0
END:VCALENDAR""",
    )

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    periodic_data_sync = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(
            user=user, ical_url="https://baserow.io/ical.ics"
        ),
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )

    assert (
        EnterpriseDataSyncHandler.sync_periodic_data_sync(periodic_data_sync.id) is True
    )

    periodic_data_sync.data_sync.refresh_from_db()
    assert periodic_data_sync.data_sync.last_sync is not None
    assert periodic_data_sync.data_sync.last_error is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_periodic_sync_disabled_on_license_loss_sends_notification(
    enterprise_data_fixture, synced_roles
):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    periodic_data_sync = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
        interval=DATA_SYNC_INTERVAL_DAILY,
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )

    enterprise_data_fixture.delete_all_licenses()

    with freeze_time("2024-10-10T12:15:00.00Z"):
        with transaction.atomic():
            EnterpriseDataSyncHandler.call_periodic_data_sync_syncs_that_are_due()

    periodic_data_sync.refresh_from_db()
    assert periodic_data_sync.interval == DATA_SYNC_INTERVAL_MANUAL
    assert periodic_data_sync.automatically_deactivated is True
    assert (
        periodic_data_sync.deactivation_reason
        == DEACTIVATION_REASON_LICENSE_UNAVAILABLE
    )

    notifications = Notification.objects.filter(
        type=PeriodicDataSyncDeactivatedNotificationType.type
    )
    assert len(notifications) == 1

    notification_data = notifications[0].data
    assert notification_data["data_sync_id"] == periodic_data_sync.data_sync_id
    assert notification_data["table_name"] == periodic_data_sync.data_sync.table.name
    assert (
        notification_data["deactivation_reason"]
        == DEACTIVATION_REASON_LICENSE_UNAVAILABLE
    )


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_periodic_sync_failure_deactivation_shows_failure_message(
    enterprise_data_fixture, synced_roles
):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    periodic_data_sync = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )

    periodic_data_sync.consecutive_failed_count = 5
    periodic_data_sync.automatically_deactivated = True
    periodic_data_sync.deactivation_reason = DEACTIVATION_REASON_FAILURE
    periodic_data_sync.save()

    with transaction.atomic():
        PeriodicDataSyncDeactivatedNotificationType.notify_authorized_user(
            periodic_data_sync
        )

    notifications = Notification.objects.filter(
        type=PeriodicDataSyncDeactivatedNotificationType.type
    )
    assert len(notifications) == 1
    notification_data = notifications[0].data
    assert notification_data["data_sync_id"] == periodic_data_sync.data_sync_id
    assert notification_data["table_name"] == periodic_data_sync.data_sync.table.name
    assert notification_data["deactivation_reason"] == DEACTIVATION_REASON_FAILURE


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@patch("baserow.contrib.database.table.signals.table_created.send")
def test_create_two_way_data_sync_table(
    send_mock, enterprise_data_fixture, create_postgresql_test_table
):
    enterprise_data_fixture.enable_enterprise()

    default_database = settings.DATABASES["default"]
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        synced_properties=[
            "id",
            "text_col",
        ],
        two_way_sync=True,
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=create_postgresql_test_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 2
    assert fields[0].primary is True
    assert fields[0].read_only is True
    assert fields[1].primary is False
    assert fields[1].read_only is False


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@patch("baserow.contrib.database.table.signals.table_created.send")
def test_create_two_way_data_sync_table_and_add_properties(
    send_mock, enterprise_data_fixture, create_postgresql_test_table
):
    enterprise_data_fixture.enable_enterprise()

    default_database = settings.DATABASES["default"]
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        synced_properties=[
            "id",
        ],
        two_way_sync=True,
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=create_postgresql_test_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 1
    assert fields[0].primary is True
    assert fields[0].read_only is True

    data_sync = handler.update_data_sync_table(
        user=user,
        data_sync=data_sync,
        synced_properties=["id", "text_col"],
        two_way_sync=True,
    )

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 2
    assert fields[0].primary is True
    assert fields[0].read_only is True
    assert fields[1].primary is False
    assert fields[1].read_only is False


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@patch("baserow.contrib.database.table.signals.table_created.send")
def test_create_and_unset_two_way_data_sync_table(
    send_mock, enterprise_data_fixture, create_postgresql_test_table
):
    enterprise_data_fixture.enable_enterprise()

    default_database = settings.DATABASES["default"]
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        synced_properties=["id", "text_col"],
        two_way_sync=True,
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=create_postgresql_test_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 2
    assert fields[0].primary is True
    assert fields[0].read_only is True
    assert fields[1].primary is False
    assert fields[1].read_only is False

    data_sync = handler.update_data_sync_table(
        user=user,
        data_sync=data_sync,
        synced_properties=["id", "text_col"],
        two_way_sync=False,
    )

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 2
    assert fields[0].primary is True
    assert fields[0].read_only is True
    assert fields[1].primary is False
    assert fields[1].read_only is True


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@patch("baserow.contrib.database.table.signals.table_created.send")
def test_create_and_set_two_way_data_sync_table(
    send_mock, enterprise_data_fixture, create_postgresql_test_table
):
    enterprise_data_fixture.enable_enterprise()

    default_database = settings.DATABASES["default"]
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        synced_properties=["id", "text_col"],
        two_way_sync=False,
        two_way_sync_consecutive_failures=3,
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=create_postgresql_test_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 2
    assert fields[0].primary is True
    assert fields[0].read_only is True
    assert fields[1].primary is False
    assert fields[1].read_only is True

    with transaction.atomic():
        data_sync = handler.update_data_sync_table(
            user=user,
            data_sync=data_sync,
            synced_properties=["id", "text_col"],
            two_way_sync=True,
        )

    # THis value should be reset when the two-way data sync is enabled.
    assert data_sync.two_way_sync_consecutive_failures == 0

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 2
    assert fields[0].primary is True
    assert fields[0].read_only is True
    assert fields[1].primary is False
    assert fields[1].read_only is False
