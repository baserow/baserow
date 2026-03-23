from django.test.utils import override_settings

import pytest

from baserow.core.notifications.models import Notification, NotificationRecipient
from baserow_enterprise.data_scanner.handler import DataScannerHandler
from baserow_enterprise.data_scanner.models import DataScan
from baserow_enterprise.data_scanner.notification_types import (
    DataScanNewResultsNotificationType,
)


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_notify_instance_admins_creates_notification(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    admin = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScan.objects.create(
        name="Test Scan", scan_type="pattern", pattern="AA", created_by=admin
    )

    recipients = DataScanNewResultsNotificationType.notify_instance_admins(scan, 5)

    assert recipients is not None
    assert len(recipients) == 1
    assert recipients[0].recipient == admin

    notification = recipients[0].notification
    assert notification.type == "data_scan_new_results"
    assert notification.data["scan_id"] == scan.id
    assert notification.data["scan_name"] == "Test Scan"
    assert notification.data["new_results_count"] == 5
    assert notification.workspace is None


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_notify_instance_admins_sends_to_all_staff(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    admin1 = enterprise_data_fixture.create_user(is_staff=True)
    admin2 = enterprise_data_fixture.create_user(is_staff=True)
    enterprise_data_fixture.create_user(is_staff=False)

    scan = DataScan.objects.create(
        name="Test", scan_type="pattern", pattern="AA", created_by=admin1
    )

    recipients = DataScanNewResultsNotificationType.notify_instance_admins(scan, 3)

    assert len(recipients) == 2
    recipient_users = {r.recipient_id for r in recipients}
    assert recipient_users == {admin1.id, admin2.id}


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_notify_instance_admins_skips_inactive_staff(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    active_admin = enterprise_data_fixture.create_user(is_staff=True)
    inactive_admin = enterprise_data_fixture.create_user(is_staff=True)
    inactive_admin.is_active = False
    inactive_admin.save()

    scan = DataScan.objects.create(
        name="Test", scan_type="pattern", pattern="AA", created_by=active_admin
    )

    recipients = DataScanNewResultsNotificationType.notify_instance_admins(scan, 1)

    assert len(recipients) == 1
    assert recipients[0].recipient == active_admin


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_notify_instance_admins_returns_none_when_no_staff(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user(is_staff=False)

    scan = DataScan.objects.create(
        name="Test", scan_type="pattern", pattern="AA", created_by=user
    )

    result = DataScanNewResultsNotificationType.notify_instance_admins(scan, 1)

    assert result is None


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_email_title_singular(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    notification = Notification(
        type="data_scan_new_results",
        data={"scan_id": 1, "scan_name": "IBAN Scanner", "new_results_count": 1},
    )

    title = DataScanNewResultsNotificationType.get_notification_title_for_email(
        notification, {}
    )
    assert "1 new result found for IBAN Scanner" in title


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_email_title_plural(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    notification = Notification(
        type="data_scan_new_results",
        data={"scan_id": 1, "scan_name": "IBAN Scanner", "new_results_count": 10},
    )

    title = DataScanNewResultsNotificationType.get_notification_title_for_email(
        notification, {}
    )
    assert "10 new results found for IBAN Scanner" in title


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_email_description(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    notification = Notification(
        type="data_scan_new_results",
        data={"scan_id": 1, "scan_name": "IBAN Scanner", "new_results_count": 3},
    )

    desc = DataScanNewResultsNotificationType.get_notification_description_for_email(
        notification, {}
    )
    assert "IBAN Scanner" in desc
    assert "3 new matches" in desc


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_scan_sends_notification_on_new_results(
    enterprise_data_fixture, populate_search_table
):
    enterprise_data_fixture.enable_enterprise()
    admin1 = enterprise_data_fixture.create_user(is_staff=True)
    admin2 = enterprise_data_fixture.create_user(is_staff=True)
    enterprise_data_fixture.create_user(is_staff=False)

    table, fields, rows = enterprise_data_fixture.build_table(
        user=admin1,
        columns=[("Name", "text")],
        rows=[["secret123"]],
    )
    field = fields[0]
    workspace = table.database.workspace

    populate_search_table(table, field, rows)

    scan = DataScannerHandler.create_scan(
        user=admin1,
        name="Secret Scanner",
        scan_type="list_of_values",
        list_items=["secret123"],
        scan_all_workspaces=False,
        workspace_ids=[workspace.id],
    )

    DataScannerHandler.run_scan(scan.id)

    scan.refresh_from_db()
    assert scan.last_error is None or scan.last_error == ""

    notifications = Notification.objects.filter(type="data_scan_new_results")
    assert notifications.count() == 1

    notification = notifications.first()
    assert notification.data["scan_id"] == scan.id
    assert notification.data["scan_name"] == "Secret Scanner"
    assert notification.data["new_results_count"] > 0

    admin_recipients = NotificationRecipient.objects.filter(notification=notification)
    recipient_ids = set(admin_recipients.values_list("recipient_id", flat=True))
    assert recipient_ids == {admin1.id, admin2.id}


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_scan_no_notification_when_no_new_results(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    admin = enterprise_data_fixture.create_user(is_staff=True)
    workspace = enterprise_data_fixture.create_workspace(user=admin)

    scan = DataScannerHandler.create_scan(
        user=admin,
        name="Empty Scanner",
        scan_type="pattern",
        pattern="AA",
        scan_all_workspaces=False,
        workspace_ids=[workspace.id],
    )

    DataScannerHandler.run_scan(scan.id)

    assert Notification.objects.filter(type="data_scan_new_results").count() == 0


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_scan_no_notification_when_only_existing_results(
    enterprise_data_fixture, populate_search_table
):
    enterprise_data_fixture.enable_enterprise()
    admin = enterprise_data_fixture.create_user(is_staff=True)

    table, fields, rows = enterprise_data_fixture.build_table(
        user=admin,
        columns=[("Name", "text")],
        rows=[["secret123"]],
    )
    field = fields[0]
    workspace = table.database.workspace

    populate_search_table(table, field, rows)

    scan = DataScannerHandler.create_scan(
        user=admin,
        name="Test",
        scan_type="list_of_values",
        list_items=["secret123"],
        scan_all_workspaces=False,
        workspace_ids=[workspace.id],
    )

    DataScannerHandler.run_scan(scan.id)
    assert Notification.objects.filter(type="data_scan_new_results").count() == 1

    Notification.objects.all().delete()

    DataScannerHandler.run_scan(scan.id)
    assert Notification.objects.filter(type="data_scan_new_results").count() == 0


@pytest.mark.data_scanner
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_run_scan_no_notification_on_error(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    admin = enterprise_data_fixture.create_user(is_staff=True)

    scan = DataScannerHandler.create_scan(
        user=admin,
        name="License Test",
        scan_type="pattern",
        pattern="AA",
    )

    from baserow.core.cache import local_cache
    from baserow_premium.license.models import License

    License.objects.all().delete()
    local_cache.clear()

    DataScannerHandler.run_scan(scan.id)

    scan.refresh_from_db()
    assert scan.last_error is not None
    assert Notification.objects.filter(type="data_scan_new_results").count() == 0
