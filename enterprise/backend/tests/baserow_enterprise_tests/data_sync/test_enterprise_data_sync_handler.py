from datetime import datetime, time, timezone
from unittest.mock import patch

from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone as django_timezone

import pytest
from baserow_premium.license.exceptions import FeaturesNotAvailableError
from baserow_premium.license.models import License
from freezegun.api import freeze_time

from baserow.contrib.database.data_sync.models import DataSync
from baserow.core.exceptions import UserNotInWorkspace
from baserow_enterprise.data_sync.handler import EnterpriseDataSyncHandler
from baserow_enterprise.data_sync.models import PeriodicDataSyncInterval


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_auto_data_sync_interval_licence_check(enterprise_data_fixture):
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
@override_settings(DEBUG=True)
def test_update_auto_data_sync_interval_check_permissions(enterprise_data_fixture):
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
@override_settings(DEBUG=True)
def test_update_auto_data_sync_interval_create(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    data_sync = enterprise_data_fixture.create_ical_data_sync(user=user)

    auto_data_sync_interval = (
        EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
            user=user,
            data_sync=data_sync,
            interval="DAILY",
            when=time(hour=12, minute=10, second=1, microsecond=1),
        )
    )

    fetched_auto_data_sync_interval = PeriodicDataSyncInterval.objects.all().first()
    assert auto_data_sync_interval.id == fetched_auto_data_sync_interval.id
    assert (
        auto_data_sync_interval.data_sync_id
        == auto_data_sync_interval.data_sync_id
        == data_sync.id
    )
    assert (
        auto_data_sync_interval.interval == auto_data_sync_interval.interval == "DAILY"
    )
    assert (
        auto_data_sync_interval.when
        == auto_data_sync_interval.when
        == time(hour=12, minute=10, second=1, microsecond=1)
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_auto_data_sync_interval_update(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    data_sync = enterprise_data_fixture.create_ical_data_sync(user=user)

    EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=data_sync,
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )

    auto_data_sync_interval = (
        EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
            user=user,
            data_sync=data_sync,
            interval="HOURLY",
            when=time(hour=14, minute=12, second=1, microsecond=1),
        )
    )

    fetched_auto_data_sync_interval = PeriodicDataSyncInterval.objects.all().first()
    assert auto_data_sync_interval.id == fetched_auto_data_sync_interval.id
    assert (
        auto_data_sync_interval.data_sync_id
        == auto_data_sync_interval.data_sync_id
        == data_sync.id
    )
    assert (
        auto_data_sync_interval.interval == auto_data_sync_interval.interval == "HOURLY"
    )
    assert (
        auto_data_sync_interval.when
        == auto_data_sync_interval.when
        == time(hour=14, minute=12, second=1, microsecond=1)
    )


@pytest.mark.django_db
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
@override_settings(DEBUG=True)
@patch("baserow_enterprise.data_sync.handler.sync_periodic_data_sync")
def test_call_periodic_data_sync_syncs_starts_task(
    mock_sync_periodic_data_sync, enterprise_data_fixture
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

    License.objects.all().delete()

    with freeze_time("2024-10-10T12:15:00.00Z"):
        with transaction.atomic():
            EnterpriseDataSyncHandler.call_periodic_data_sync_syncs_that_are_due()

    not_yet_executed_1.refresh_from_db()
    # Should not be triggered because there was no license.
    assert not_yet_executed_1.last_periodic_sync is None


@pytest.mark.django_db(transaction=True, databases=["default", "default-copy"])
@override_settings(DEBUG=True)
def test_skip_locked_data_syncs(enterprise_data_fixture):
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
