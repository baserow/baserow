import pytest

from baserow.core.abuse_reports.models import AbuseReport
from baserow.core.abuse_reports.notification_types import (
    AbuseReportCreatedNotificationType,
)
from baserow.core.emails import prevent_autolink
from baserow.core.notifications.models import NotificationRecipient


def create_report(data_fixture, **kwargs):
    workspace = kwargs.pop("workspace", None) or data_fixture.create_workspace()
    values = {
        "resource_type": "database_view",
        "resource_id": 42,
        "resource_name": "Shared view",
        "workspace": workspace,
        "workspace_name": workspace.name,
        "public_url": "http://localhost:3000/public/grid/some-slug",
        "reporter_name": "John Doe",
        "reporter_email": "john@example.com",
        "description": "This view is used for phishing.",
        **kwargs,
    }
    return AbuseReport.objects.create(**values)


@pytest.mark.django_db
def test_notify_instance_admins_creates_notifications_for_active_staff(data_fixture):
    admin_1 = data_fixture.create_user(is_staff=True)
    admin_2 = data_fixture.create_user(is_staff=True)
    data_fixture.create_user()
    data_fixture.create_user(is_staff=True, is_active=False)
    report = create_report(data_fixture)

    AbuseReportCreatedNotificationType.notify_instance_admins(report)

    recipients = NotificationRecipient.objects.filter(
        notification__type=AbuseReportCreatedNotificationType.type
    ).order_by("recipient_id")
    assert [nr.recipient_id for nr in recipients] == [admin_1.id, admin_2.id]

    notification = recipients[0].notification
    assert notification.workspace_id is None
    assert notification.sender_id is None
    assert notification.data == {
        "resource_type": "database_view",
        "resource_id": 42,
        "resource_name": "Shared view",
        "workspace_id": report.workspace_id,
        "workspace_name": report.workspace_name,
        "public_url": "http://localhost:3000/public/grid/some-slug",
        "reporter_name": "John Doe",
        "reporter_email": "john@example.com",
        "description": "This view is used for phishing.",
    }


@pytest.mark.django_db
def test_notify_instance_admins_without_admins(data_fixture):
    data_fixture.create_user()
    report = create_report(data_fixture)

    assert AbuseReportCreatedNotificationType.notify_instance_admins(report) is None


@pytest.mark.django_db
def test_email_title_and_description_neutralize_untrusted_text(data_fixture):
    data_fixture.create_user(is_staff=True)
    report = create_report(
        data_fixture,
        resource_name="phishing.example.com",
        reporter_email="attacker@evil.com",
        description="Visit malicious.example.com now! " * 20,
        public_url="http://baserow.example.com/public/grid/some-slug",
    )
    recipients = AbuseReportCreatedNotificationType.notify_instance_admins(report)
    notification = recipients[0].notification

    title = AbuseReportCreatedNotificationType.get_notification_title_for_email(
        notification, {}
    )
    assert prevent_autolink("phishing.example.com") in title
    assert "phishing.example.com" not in title

    description = (
        AbuseReportCreatedNotificationType.get_notification_description_for_email(
            notification, {}
        )
    )
    assert prevent_autolink("attacker@evil.com") in description
    assert "malicious.example.com" not in description
    # Long descriptions are truncated so a report can't flood the email.
    assert len(description) < 500

    # The reported URL comes first so that the truncated description can't push it
    # out of sight, and is de-linkified so that it can't be opened with a single
    # click.
    reported_url = prevent_autolink("http://baserow.example.com/public/grid/some-slug")
    assert description.startswith(reported_url)
    assert "http://baserow.example.com/public/grid/some-slug" not in description


@pytest.mark.django_db
def test_email_does_not_link_to_the_reported_page(data_fixture):
    data_fixture.create_user(is_staff=True)
    report = create_report(data_fixture)
    recipients = AbuseReportCreatedNotificationType.notify_instance_admins(report)
    notification = recipients[0].notification

    # The summary email turns the notification title into a link to this URL, and
    # it must never point to the reported page because it's suspected of phishing.
    notification_type = AbuseReportCreatedNotificationType()
    assert notification_type.get_web_frontend_url(notification) is None


@pytest.mark.django_db
def test_notify_instance_admins_marks_report_as_notified(data_fixture):
    report = create_report(data_fixture)

    assert AbuseReportCreatedNotificationType.notify_instance_admins(report) is None
    assert report.admins_notified is False

    data_fixture.create_user(is_staff=True)
    assert AbuseReportCreatedNotificationType.notify_instance_admins(report) is not None
    report.refresh_from_db()
    assert report.admins_notified is True
