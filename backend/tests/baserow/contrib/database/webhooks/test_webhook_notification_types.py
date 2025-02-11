import pytest

from baserow.contrib.database.webhooks.notification_types import (
    WebhookDeactivatedNotificationType,
)


@pytest.mark.django_db(transaction=True)
def test_webhook_deactivated_notification_can_be_render_as_email(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    webhook = data_fixture.create_table_webhook(
        table=table, active=True, failed_triggers=1
    )

    notification_recipients = (
        WebhookDeactivatedNotificationType.notify_admins_in_workspace(webhook)
    )
    notification = notification_recipients[0].notification

    assert WebhookDeactivatedNotificationType.get_notification_title_for_email(
        notification, {}
    ) == "%(name)s webhook has been deactivated." % {
        "name": notification.data["webhook_name"],
    }

    assert (
        WebhookDeactivatedNotificationType.get_notification_description_for_email(
            notification, {}
        )
        == "The webhook failed more than 8 consecutive times and "
        "was therefore deactivated."
    )
