from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from rest_framework.status import (
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from baserow.core.abuse_reports.models import AbuseReport
from baserow.core.handler import CoreHandler

VALID_DESCRIPTION = (
    "This application is used for phishing. It pretends to be the login page of "
    "another company and asks visitors to fill out their credentials."
)


def submit_report(api_client, domain_name, **kwargs):
    values = {
        "resource_type": "builder",
        "identifier": domain_name,
        "name": "John Doe",
        "email": "john@example.com",
        "description": VALID_DESCRIPTION,
        **kwargs,
    }
    return api_client.post(reverse("api:abuse_reports:create"), values, format="json")


def create_published_domain(data_fixture, user, **kwargs):
    builder = data_fixture.create_builder_application(user=user, **kwargs)
    return data_fixture.create_builder_custom_domain(
        builder=builder,
        domain_name="phishing.example.com",
        published_to=data_fixture.create_builder_application(workspace=None),
    )


@pytest.mark.django_db
@override_settings(PUBLIC_WEB_FRONTEND_URL="https://baserow.example:8443")
def test_anonymous_user_can_report_published_builder(api_client, data_fixture):
    user = data_fixture.create_user()
    domain = create_published_domain(data_fixture, user, name="Shared application")
    builder = domain.builder

    response = submit_report(api_client, "phishing.example.com")

    assert response.status_code == HTTP_204_NO_CONTENT
    report = AbuseReport.objects.get()
    assert report.resource_type == "builder"
    assert report.resource_id == builder.id
    assert report.resource_name == "Shared application"
    assert report.workspace_id == builder.workspace_id
    assert report.workspace_name == builder.workspace.name
    assert report.public_url == "https://phishing.example.com:8443"
    assert report.reporter_name == "John Doe"
    assert report.reporter_email == "john@example.com"
    assert report.description == VALID_DESCRIPTION


@pytest.mark.django_db
def test_report_keeps_the_builder_id_when_republished(api_client, data_fixture):
    user = data_fixture.create_user()
    domain = create_published_domain(data_fixture, user)

    assert submit_report(api_client, domain.domain_name).status_code == (
        HTTP_204_NO_CONTENT
    )

    domain.published_to = data_fixture.create_builder_application(workspace=None)
    domain.save()

    assert submit_report(api_client, domain.domain_name).status_code == (
        HTTP_204_NO_CONTENT
    )
    assert list(AbuseReport.objects.values_list("resource_id", flat=True)) == [
        domain.builder_id,
        domain.builder_id,
    ]


@pytest.mark.django_db
def test_report_unknown_domain(api_client, data_fixture):
    user = data_fixture.create_user()
    create_published_domain(data_fixture, user)

    response = submit_report(api_client, "unknown.example.com")

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_BUILDER_DOES_NOT_EXIST"
    assert AbuseReport.objects.count() == 0


@pytest.mark.django_db
def test_report_unpublished_domain(api_client, data_fixture):
    user = data_fixture.create_user()
    data_fixture.create_builder_custom_domain(
        user=user, domain_name="draft.example.com"
    )

    response = submit_report(api_client, "draft.example.com")

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_BUILDER_DOES_NOT_EXIST"
    assert AbuseReport.objects.count() == 0


@pytest.mark.django_db
def test_report_trashed_builder(api_client, data_fixture):
    user = data_fixture.create_user()
    domain = create_published_domain(data_fixture, user)
    CoreHandler().delete_application(user, domain.builder)

    response = submit_report(api_client, domain.domain_name)

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_BUILDER_DOES_NOT_EXIST"
    assert AbuseReport.objects.count() == 0


@pytest.mark.django_db
def test_report_published_builder_when_reporting_disabled(api_client, data_fixture):
    user = data_fixture.create_user()
    domain = create_published_domain(data_fixture, user)
    CoreHandler().update_settings(
        data_fixture.create_user(is_staff=True), allow_reporting_abuse=False
    )

    response = submit_report(api_client, domain.domain_name)

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_ABUSE_REPORTING_DISABLED"
    assert AbuseReport.objects.count() == 0
