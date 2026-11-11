from django.test.utils import override_settings

import pytest
from rest_framework.reverse import reverse
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.dashboard.actions import UpdateDashboardSharingActionType
from baserow.core.action.models import Action


def premium_attributes_url(dashboard_id):
    return reverse(
        "api:premium:dashboard:premium_dashboard_attributes",
        kwargs={"dashboard_id": dashboard_id},
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_premium_dashboard_attributes_hide_logo(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    dashboard = premium_data_fixture.create_dashboard_application(user=user)

    response = api_client.patch(
        premium_attributes_url(dashboard.id),
        data={"show_logo": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["type"] == "dashboard"
    assert response_json["show_logo"] is False
    dashboard.refresh_from_db()
    assert dashboard.show_logo is False
    # Registered as a sharing change, so the audit log doesn't report a rename.
    assert Action.objects.get().type == UpdateDashboardSharingActionType.type


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_premium_dashboard_attributes_without_premium_license(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=False
    )
    dashboard = premium_data_fixture.create_dashboard_application(user=user)

    response = api_client.patch(
        premium_attributes_url(dashboard.id),
        data={"show_logo": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
    assert response.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"
    dashboard.refresh_from_db()
    assert dashboard.show_logo is True


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_premium_dashboard_attributes_template(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    workspace = premium_data_fixture.create_workspace(user=user)
    premium_data_fixture.create_template(workspace=workspace)
    dashboard = premium_data_fixture.create_dashboard_application(workspace=workspace)

    response = api_client.patch(
        premium_attributes_url(dashboard.id),
        data={"show_logo": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert (
        response.json()["error"] == "ERROR_CANNOT_UPDATE_PREMIUM_ATTRIBUTES_ON_TEMPLATE"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_premium_dashboard_attributes_user_not_in_workspace(
    api_client, premium_data_fixture
):
    user = premium_data_fixture.create_user()
    _, other_token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    dashboard = premium_data_fixture.create_dashboard_application(user=user)

    response = api_client.patch(
        premium_attributes_url(dashboard.id),
        data={"show_logo": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"
    dashboard.refresh_from_db()
    assert dashboard.show_logo is True


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_premium_dashboard_attributes_dashboard_does_not_exist(
    api_client, premium_data_fixture
):
    _, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )

    response = api_client.patch(
        premium_attributes_url(0),
        data={"show_logo": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DOES_NOT_EXIST"
