from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from freezegun import freeze_time
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_404_NOT_FOUND,
)

from baserow_enterprise.license_types import EnterpriseLicenseType


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ["users", "action_types", "list"])
@override_settings(DEBUG=True)
def test_workspace_admins_cannot_access_workspace_audit_log_endpoints_without_an_enterprise_license(
    api_client, enterprise_data_fixture, url_name
):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)

    response = api_client.get(
        reverse(f"api:enterprise:audit_log:{url_name}")
        + f"?workspace_id={workspace.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_workspace_admins_cannot_export_workspace_audit_log_without_an_enterprise_license(
    api_client, enterprise_data_fixture
):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)

    response = api_client.post(
        reverse(f"api:enterprise:audit_log:async_export"),
        {"filter_workspace_id": workspace.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ["users", "action_types", "list"])
@override_settings(DEBUG=True)
def test_non_admins_cannot_access_workspace_audit_log_endpoints(
    api_client, enterprise_data_fixture, synced_roles, url_name
):
    enterprise_data_fixture.enable_enterprise()

    admin = enterprise_data_fixture.create_user()
    builder, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(
        user=admin, custom_permissions=[(builder, "BUILDER")]
    )

    response = api_client.get(
        reverse(f"api:enterprise:audit_log:{url_name}")
        + f"?workspace_id={workspace.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_non_admins_cannot_export_workspace_audit_log_to_csv(
    api_client, enterprise_data_fixture, synced_roles
):
    enterprise_data_fixture.enable_enterprise()

    admin = enterprise_data_fixture.create_user()
    builder, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(
        user=admin, custom_permissions=[(builder, "BUILDER")]
    )

    response = api_client.post(
        reverse("api:enterprise:audit_log:async_export"),
        {"filter_workspace_id": workspace.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ["users", "action_types", "list"])
@override_settings(DEBUG=True)
def test_workspace_audit_log_endpoints_raise_404_if_workspace_doesnt_exist(
    api_client, enterprise_data_fixture, url_name
):
    enterprise_data_fixture.enable_enterprise()

    _, token = enterprise_data_fixture.create_user_and_token()

    response = api_client.get(
        reverse(f"api:enterprise:audit_log:{url_name}") + "?workspace_id=9999",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_workspace_audit_log_export_raise_404_if_workspace_doesnt_exist(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()

    _, token = enterprise_data_fixture.create_user_and_token()

    response = api_client.post(
        reverse(f"api:enterprise:audit_log:async_export"),
        {"filter_workspace_id": 9999},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_workspace_audit_log_user_filter_returns_only_workspace_users(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()

    admin, token = enterprise_data_fixture.create_user_and_token(email="admin@test.com")
    user_wp1 = enterprise_data_fixture.create_user(email="user_wp1@test.com")
    user_wp2 = enterprise_data_fixture.create_user(email="user_wp2@test.com")

    workspace_1 = enterprise_data_fixture.create_workspace(users=[admin, user_wp1])
    workspace_2 = enterprise_data_fixture.create_workspace(users=[admin, user_wp2])

    # no search query should return all users for worspace 1
    response = api_client.get(
        reverse("api:enterprise:audit_log:users") + f"?workspace_id={workspace_1.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {"id": admin.id, "value": admin.email},
            {"id": user_wp1.id, "value": user_wp1.email},
        ],
    }

    # no search query should return all users for worspace 2
    response = api_client.get(
        reverse("api:enterprise:audit_log:users") + f"?workspace_id={workspace_2.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {"id": admin.id, "value": admin.email},
            {"id": user_wp2.id, "value": user_wp2.email},
        ],
    }

    # searching by email should return only the correct user
    response = api_client.get(
        reverse("api:enterprise:audit_log:users")
        + f"?workspace_id={workspace_1.id}&search=user",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{"id": user_wp1.id, "value": "user_wp1@test.com"}],
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
@pytest.mark.parametrize("url_name", ["users", "action_types", "list"])
def test_staff_member_can_access_audit_log_for_their_own_workspace(
    api_client,
    enterprise_data_fixture,
    alternative_per_workspace_license_service,
    url_name,
):
    admin_user, admin_token = enterprise_data_fixture.create_user_and_token(
        email="admin@test.com", is_staff=True
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin_user)
    alternative_per_workspace_license_service.restrict_user_license_to(
        admin_user, EnterpriseLicenseType.type, workspace.id
    )
    response = api_client.get(
        reverse(f"api:enterprise:audit_log:{url_name}")
        + f"?workspace_id={workspace.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@override_settings(DEBUG=True)
@pytest.mark.parametrize("url_name", ["users", "action_types", "list"])
def test_staff_member_can_access_audit_log_for_any_workspace(
    api_client,
    enterprise_data_fixture,
    url_name,
):
    enterprise_data_fixture.enable_enterprise()
    admin_user, admin_token = enterprise_data_fixture.create_user_and_token(
        email="admin@test.com", is_staff=True
    )
    other_user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=other_user)
    response = api_client.get(
        reverse(f"api:enterprise:audit_log:{url_name}")
        + f"?workspace_id={workspace.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@override_settings(DEBUG=True)
@pytest.mark.parametrize("url_name", ["users", "action_types", "list"])
def test_staff_member_cant_access_audit_log_for_own_workspace_without_license(
    api_client,
    enterprise_data_fixture,
    alternative_per_workspace_license_service,
    url_name,
):
    admin_user, admin_token = enterprise_data_fixture.create_user_and_token(
        email="admin@test.com", is_staff=True
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin_user)
    response = api_client.get(
        reverse(f"api:enterprise:audit_log:{url_name}")
        + f"?workspace_id={workspace.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_workspace_audit_log_can_export_to_csv_filtered_entries(
    api_client,
    enterprise_data_fixture,
    synced_roles,
    django_capture_on_commit_callbacks,
):
    enterprise_data_fixture.enable_enterprise()

    admin_user, admin_token = enterprise_data_fixture.create_user_and_token(
        email="admin@test.com"
    )
    workspace = enterprise_data_fixture.create_workspace(user=admin_user)

    csv_settings = {
        "csv_column_separator": "|",
        "csv_first_row_header": False,
        "export_charset": "utf-8",
    }
    filters = {
        "filter_user_id": admin_user.id,
        "filter_action_type": "create_application",
        "filter_from_timestamp": "2023-01-01T00:00:00Z",
        "filter_to_timestamp": "2023-01-03T00:00:00Z",
        "filter_workspace_id": workspace.id,
        "exclude_columns": "workspace_id,workspace_name",
    }

    # if the action type is invalid, it should return a 400
    response = api_client.post(
        reverse("api:enterprise:audit_log:async_export"),
        data={**csv_settings, "filter_action_type": "wrong_type"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST

    # if the workspace id is invalid, it should return a 404
    response = api_client.post(
        reverse("api:enterprise:audit_log:async_export"),
        data={**csv_settings, **filters, "filter_workspace_id": 9999},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND

    with freeze_time("2023-01-02 12:00"), django_capture_on_commit_callbacks(
        execute=True
    ):
        admin_token = enterprise_data_fixture.generate_token(admin_user)
        response = api_client.post(
            reverse("api:enterprise:audit_log:async_export"),
            data={**csv_settings, **filters},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {admin_token}",
        )
    assert response.status_code == HTTP_202_ACCEPTED, response.json()
    job = response.json()
    assert job["id"] is not None
    assert job["state"] == "pending"
    assert job["type"] == "audit_log_export"

    admin_token = enterprise_data_fixture.generate_token(admin_user)
    response = api_client.get(
        reverse(
            "api:jobs:item",
            kwargs={"job_id": job["id"]},
        ),
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    job = response.json()
    assert job["state"] == "finished"
    assert job["type"] == "audit_log_export"
    for key, value in csv_settings.items():
        assert job[key] == value
    for key in [
        "filter_user_id",
        "filter_action_type",
        "filter_from_timestamp",
        "filter_to_timestamp",
    ]:
        assert job[key] == filters[key]

    assert job["exported_file_name"].endswith(".csv")
    assert job["url"].startswith("http://localhost:8000/media/export_files/")
    assert job["created_on"] == "2023-01-02T12:00:00Z"

    # These filters are automatically added by the workspace endpoint
    assert job["filter_workspace_id"] == workspace.id
    assert job["exclude_columns"] == "workspace_id,workspace_name"
