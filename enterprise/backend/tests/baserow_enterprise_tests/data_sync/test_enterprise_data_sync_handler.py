from datetime import time

from django.test.utils import override_settings

import pytest
from baserow_premium.license.exceptions import FeaturesNotAvailableError

from baserow.core.exceptions import UserNotInWorkspace
from baserow_enterprise.data_sync.handler import EnterpriseDataSyncHandler
from baserow_enterprise.data_sync.models import AutoDataSyncInterval


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_auto_data_sync_interval_licence_check(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    data_sync = enterprise_data_fixture.create_ical_data_sync(user=user)

    with pytest.raises(FeaturesNotAvailableError):
        EnterpriseDataSyncHandler.update_auto_data_sync_interval(
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
        EnterpriseDataSyncHandler.update_auto_data_sync_interval(
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

    auto_data_sync_interval = EnterpriseDataSyncHandler.update_auto_data_sync_interval(
        user=user,
        data_sync=data_sync,
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )

    fetched_auto_data_sync_interval = AutoDataSyncInterval.objects.all().first()
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

    EnterpriseDataSyncHandler.update_auto_data_sync_interval(
        user=user,
        data_sync=data_sync,
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )

    auto_data_sync_interval = EnterpriseDataSyncHandler.update_auto_data_sync_interval(
        user=user,
        data_sync=data_sync,
        interval="HOURLY",
        when=time(hour=14, minute=12, second=1, microsecond=1),
    )

    fetched_auto_data_sync_interval = AutoDataSyncInterval.objects.all().first()
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
