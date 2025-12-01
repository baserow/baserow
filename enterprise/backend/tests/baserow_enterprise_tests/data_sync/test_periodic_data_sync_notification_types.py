from datetime import time

from django.test.utils import override_settings

import pytest

from baserow_enterprise.data_sync.handler import EnterpriseDataSyncHandler
from baserow_enterprise.data_sync.notification_types import (
    PeriodicDataSyncDeactivatedNotificationType,
)


@override_settings(DEBUG=True)
@pytest.mark.django_db(transaction=True)
def test_webhook_deactivated_notification_can_be_render_as_email(
    api_client, enterprise_data_fixture, synced_roles
):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    periodic_data_sync = EnterpriseDataSyncHandler.update_periodic_data_sync_interval(
        user=user,
        data_sync=enterprise_data_fixture.create_ical_data_sync(user=user),
        interval="DAILY",
        when=time(hour=12, minute=10, second=1, microsecond=1),
    )

    notification_recipients = (
        PeriodicDataSyncDeactivatedNotificationType.notify_authorized_user(
            periodic_data_sync
        )
    )
    notification = notification_recipients[0].notification

    assert PeriodicDataSyncDeactivatedNotificationType.get_notification_title_for_email(
        notification, {}
    ) == "%(name)s periodic data sync has been deactivated." % {
        "name": periodic_data_sync.data_sync.table.name,
    }

    assert (
        PeriodicDataSyncDeactivatedNotificationType.get_notification_description_for_email(
            notification, {}
        )
        == "The periodic data sync failed more than 4 consecutive times"
        " and was therefore deactivated."
    )
