from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from rest_framework.status import (
    HTTP_204_NO_CONTENT,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.dashboard.handler import DashboardHandler
from baserow.core.abuse_reports.models import AbuseReport
from baserow.core.handler import CoreHandler

VALID_DESCRIPTION = (
    "This dashboard is used for phishing. It pretends to be the statistics page of "
    "another company and links its visitors to a fake login page."
)


def submit_report(api_client, dashboard, **kwargs):
    values = {
        "resource_type": "dashboard",
        "identifier": dashboard.slug,
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
@override_settings(BASEROW_EMBEDDED_SHARE_URL="https://embed.example/baserow/")
def test_anonymous_user_can_report_public_dashboard(api_client, data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(
        user=user, name="Shared dashboard", public=True
    )

    response = submit_report(api_client, dashboard)

    assert response.status_code == HTTP_204_NO_CONTENT
    report = AbuseReport.objects.get()
    assert report.resource_type == "dashboard"
    assert report.resource_id == dashboard.id
    assert report.resource_name == "Shared dashboard"
    assert report.workspace_id == dashboard.workspace_id
    assert report.workspace_name == dashboard.workspace.name
    assert report.public_url == (
        f"https://embed.example/baserow/public/dashboard/{dashboard.slug}"
    )
    assert report.reporter_name == "John Doe"
    assert report.reporter_email == "john@example.com"
    assert report.description == VALID_DESCRIPTION


@pytest.mark.django_db
def test_report_unknown_dashboard_slug(api_client, data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user, public=True)

    response = submit_report(api_client, dashboard, identifier="unknown-slug")

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DOES_NOT_EXIST"
    assert AbuseReport.objects.count() == 0


@pytest.mark.django_db
def test_report_private_dashboard(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user, public=False)

    response = submit_report(api_client, dashboard)

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DOES_NOT_EXIST"

    # A workspace member can resolve a private dashboard by its slug, but must not
    # be able to report it.
    response = submit_report(api_client, dashboard, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DOES_NOT_EXIST"
    assert AbuseReport.objects.count() == 0


@pytest.mark.django_db
def test_report_trashed_dashboard(api_client, data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user, public=True)
    CoreHandler().delete_application(user, dashboard)

    response = submit_report(api_client, dashboard)

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DOES_NOT_EXIST"
    assert AbuseReport.objects.count() == 0


@pytest.mark.django_db
def test_report_password_protected_dashboard(api_client, data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user, public=True)
    dashboard.set_password("12345678")
    dashboard.save()
    token = DashboardHandler().encode_public_access_token(dashboard)

    response = submit_report(api_client, dashboard)

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_AUTHORIZATION_TO_PUBLIC_DASHBOARD"
    assert AbuseReport.objects.count() == 0

    response = submit_report(
        api_client, dashboard, HTTP_BASEROW_DASHBOARD_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    assert AbuseReport.objects.count() == 1
