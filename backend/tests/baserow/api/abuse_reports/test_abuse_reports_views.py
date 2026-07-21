from datetime import timedelta
from unittest.mock import patch

from django.shortcuts import reverse
from django.test.utils import override_settings
from django.utils import timezone

import pytest
from rest_framework.status import (
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
    HTTP_429_TOO_MANY_REQUESTS,
)

from baserow.core.abuse_reports.models import AbuseReport
from baserow.core.handler import CoreHandler
from baserow.core.notifications.models import NotificationRecipient

VALID_DESCRIPTION = (
    "This view is used for phishing. It pretends to be the login page of another "
    "company and asks visitors to fill out their credentials."
)


def submit_report(api_client, view, **kwargs):
    values = {
        "resource_type": "database_view",
        "identifier": view.slug,
        "name": "John Doe",
        "email": "john@example.com",
        "description": VALID_DESCRIPTION,
        **kwargs,
    }
    extra = {key: values.pop(key) for key in list(values) if key.startswith("HTTP_")}
    return api_client.post(
        reverse("api:abuse_reports:create"), values, format="json", **extra
    )


@pytest.mark.django_db
def test_anonymous_user_can_report_public_grid_view(api_client, data_fixture):
    user = data_fixture.create_user()
    view = data_fixture.create_grid_view(user=user, public=True, name="Shared grid")

    response = submit_report(api_client, view)

    assert response.status_code == HTTP_204_NO_CONTENT
    report = AbuseReport.objects.get()
    assert report.resource_type == "database_view"
    assert report.resource_id == view.id
    assert report.resource_name == "Shared grid"
    assert report.workspace_id == view.table.database.workspace_id
    assert report.workspace_name == view.table.database.workspace.name
    assert report.public_url.endswith(f"/public/grid/{view.slug}")
    assert report.reporter_name == "John Doe"
    assert report.reporter_email == "john@example.com"
    assert report.description == VALID_DESCRIPTION
    assert report.ip_address == "127.0.0.1"


@pytest.mark.django_db
def test_anonymous_user_can_report_public_form_view(api_client, data_fixture):
    user = data_fixture.create_user()
    view = data_fixture.create_form_view(user=user, public=True)

    response = submit_report(api_client, view)

    assert response.status_code == HTTP_204_NO_CONTENT
    report = AbuseReport.objects.get()
    assert report.public_url.endswith(f"/form/{view.slug}")


@pytest.mark.django_db
def test_report_creates_notification_for_active_staff_users_only(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    admin = data_fixture.create_user(is_staff=True)
    data_fixture.create_user(is_staff=True, is_active=False)
    view = data_fixture.create_grid_view(user=user, public=True)

    response = submit_report(api_client, view)

    assert response.status_code == HTTP_204_NO_CONTENT
    recipients = NotificationRecipient.objects.filter(
        notification__type="abuse_report_created"
    )
    assert [nr.recipient_id for nr in recipients] == [admin.id]
    notification = recipients[0].notification
    assert notification.workspace_id is None
    assert notification.sender_id is None
    assert notification.data["resource_id"] == view.id
    assert notification.data["reporter_email"] == "john@example.com"


@pytest.mark.django_db
def test_report_registers_action_with_anonymous_user(api_client, data_fixture):
    user = data_fixture.create_user()
    view = data_fixture.create_grid_view(user=user, public=True)

    with patch(
        "baserow.core.abuse_reports.actions.SubmitAbuseReportActionType.register_action"
    ) as mock_register:
        response = submit_report(api_client, view)

    assert response.status_code == HTTP_204_NO_CONTENT
    mock_register.assert_called_once()
    call_user = mock_register.call_args[0][0]
    assert call_user.is_anonymous
    call_params = mock_register.call_args[0][1]
    assert call_params.resource_id == view.id
    assert call_params.reporter_email == "john@example.com"
    assert (
        mock_register.call_args.kwargs["workspace"].id
        == view.table.database.workspace_id
    )


@pytest.mark.django_db
def test_report_with_unknown_resource_type(api_client, data_fixture):
    user = data_fixture.create_user()
    view = data_fixture.create_grid_view(user=user, public=True)

    response = submit_report(api_client, view, resource_type="unknown")

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_ABUSE_REPORT_RESOURCE_TYPE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_report_with_unknown_slug(api_client, data_fixture):
    user = data_fixture.create_user()
    view = data_fixture.create_grid_view(user=user, public=True)

    response = submit_report(api_client, view, identifier="unknown-slug")

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"
    assert AbuseReport.objects.count() == 0


@pytest.mark.django_db
def test_report_non_public_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    view = data_fixture.create_grid_view(user=user, public=False)

    response = submit_report(api_client, view)

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"

    # An authenticated workspace member can resolve a non public view via the slug,
    # but must not be able to report it.
    response = submit_report(api_client, view, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_VIEW_DOES_NOT_EXIST"
    assert AbuseReport.objects.count() == 0


@pytest.mark.django_db
def test_report_password_protected_view(api_client, data_fixture):
    user = data_fixture.create_user()
    view, token = data_fixture.create_public_password_protected_grid_view_with_token(
        user=user, password="12345678"
    )

    response = submit_report(api_client, view)
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW"

    response = submit_report(
        api_client, view, HTTP_BASEROW_VIEW_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_report_body_validation(api_client, data_fixture):
    user = data_fixture.create_user()
    view = data_fixture.create_grid_view(user=user, public=True)

    response = submit_report(api_client, view, email="not-an-email")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = api_client.post(
        reverse("api:abuse_reports:create"),
        {"resource_type": "database_view", "identifier": view.slug},
        format="json",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = submit_report(api_client, view, description="x" * 1001)
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = submit_report(api_client, view, description="too short")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    # Longer than the model field, which must result in a validation error instead
    # of a database error.
    response = submit_report(api_client, view, email="a" * 250 + "@example.com")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_report_when_reporting_disabled(api_client, data_fixture):
    user = data_fixture.create_user()
    view = data_fixture.create_grid_view(user=user, public=True)
    settings = CoreHandler().get_settings()
    settings.allow_reporting_abuse = False
    settings.save()

    response = submit_report(api_client, view)

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_ABUSE_REPORTING_DISABLED"
    assert AbuseReport.objects.count() == 0
    assert not NotificationRecipient.objects.filter(
        notification__type="abuse_report_created"
    ).exists()


@pytest.mark.django_db
@override_settings(BASEROW_ABUSE_REPORT_THROTTLE_RATE="1/hour")
def test_report_is_rate_limited_per_ip(api_client, data_fixture):
    user = data_fixture.create_user()
    view = data_fixture.create_grid_view(user=user, public=True)

    response = submit_report(api_client, view)
    assert response.status_code == HTTP_204_NO_CONTENT

    response = submit_report(api_client, view)
    assert response.status_code == HTTP_429_TOO_MANY_REQUESTS

    response = submit_report(api_client, view, HTTP_X_FORWARDED_FOR="10.0.0.2")
    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_admins_are_not_notified_again_within_cooldown(api_client, data_fixture):
    user = data_fixture.create_user()
    data_fixture.create_user(is_staff=True)
    view = data_fixture.create_grid_view(user=user, public=True)
    other_view = data_fixture.create_grid_view(user=user, public=True)

    response = submit_report(api_client, view)
    assert response.status_code == HTTP_204_NO_CONTENT
    response = submit_report(api_client, view)
    assert response.status_code == HTTP_204_NO_CONTENT

    assert AbuseReport.objects.count() == 2
    assert (
        NotificationRecipient.objects.filter(
            notification__type="abuse_report_created"
        ).count()
        == 1
    )

    response = submit_report(api_client, other_view)
    assert response.status_code == HTTP_204_NO_CONTENT
    assert (
        NotificationRecipient.objects.filter(
            notification__type="abuse_report_created"
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_report_without_admins_does_not_count_towards_cooldown(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    view = data_fixture.create_grid_view(user=user, public=True)

    response = submit_report(api_client, view)
    assert response.status_code == HTTP_204_NO_CONTENT
    assert AbuseReport.objects.get().admins_notified is False

    data_fixture.create_user(is_staff=True)

    response = submit_report(api_client, view)
    assert response.status_code == HTTP_204_NO_CONTENT
    assert (
        NotificationRecipient.objects.filter(
            notification__type="abuse_report_created"
        ).count()
        == 1
    )
    assert AbuseReport.objects.filter(admins_notified=True).count() == 1


@pytest.mark.django_db
def test_admins_are_notified_again_after_cooldown(api_client, data_fixture):
    user = data_fixture.create_user()
    data_fixture.create_user(is_staff=True)
    view = data_fixture.create_grid_view(user=user, public=True)

    response = submit_report(api_client, view)
    assert response.status_code == HTTP_204_NO_CONTENT
    AbuseReport.objects.update(created_on=timezone.now() - timedelta(days=2))

    response = submit_report(api_client, view)
    assert response.status_code == HTTP_204_NO_CONTENT
    assert (
        NotificationRecipient.objects.filter(
            notification__type="abuse_report_created"
        ).count()
        == 2
    )
