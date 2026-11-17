from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_404_NOT_FOUND,
)

from baserow_enterprise.audit_log.models import AuditLogEntry
from baserow_enterprise.automatic_snapshots.models import AutomaticSnapshotSchedule
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role

DAILY = {"interval": "DAY", "hour": 2, "minute": 0}


def application_url(application):
    return reverse(
        "api:enterprise:automatic_snapshots:application",
        kwargs={"application_id": application.id},
    )


def workspace_url(workspace):
    return reverse(
        "api:enterprise:automatic_snapshots:workspace",
        kwargs={"workspace_id": workspace.id},
    )


def bulk_url(workspace):
    return reverse(
        "api:enterprise:automatic_snapshots:workspace_bulk",
        kwargs={"workspace_id": workspace.id},
    )


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


@pytest.mark.django_db
def test_application_schedule_lifecycle(api_client, enterprise_data_fixture):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    response = api_client.get(application_url(database), **auth)
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "state": "workspace_default",
        "schedule": None,
        "workspace_default": None,
        "min_interval_minutes": 60,
    }

    response = api_client.patch(
        application_url(database), {"enabled": False}, format="json", **auth
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert (
        response.json()["error"] == "ERROR_AUTOMATIC_SNAPSHOT_SCHEDULE_DOES_NOT_EXIST"
    )

    response = api_client.post(application_url(database), DAILY, format="json", **auth)
    assert response.status_code == HTTP_200_OK, response.json()
    created = response.json()
    assert created["application_id"] == database.id
    assert created["interval"] == "DAY"
    assert "keep_count" not in created
    assert created["enabled"] is True
    assert created["next_run_at"] is not None

    response = api_client.patch(
        application_url(database), {"enabled": False}, format="json", **auth
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["enabled"] is False

    response = api_client.get(application_url(database), **auth)
    assert response.json()["state"] == "off"
    assert response.json()["schedule"]["id"] == created["id"]

    response = api_client.delete(application_url(database), **auth)
    assert response.status_code == HTTP_204_NO_CONTENT
    assert not AutomaticSnapshotSchedule.objects.exists()

    assert list(
        AuditLogEntry.objects.filter(workspace_id=workspace.id)
        .order_by("id")
        .values_list("action_type", flat=True)
    ) == [
        "create_application_automatic_snapshot_schedule",
        "update_application_automatic_snapshot_schedule",
        "delete_application_automatic_snapshot_schedule",
    ]
    update_entry = AuditLogEntry.objects.get(
        action_type="update_application_automatic_snapshot_schedule"
    )
    assert update_entry.action_params["original_values"]["enabled"] is True
    assert update_entry.action_params["values"]["enabled"] is False


@pytest.mark.django_db
def test_workspace_default_lifecycle(api_client, enterprise_data_fixture):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    response = api_client.post(workspace_url(workspace), DAILY, format="json", **auth)
    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json()["application_id"] is None

    response = api_client.post(workspace_url(workspace), DAILY, format="json", **auth)
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert (
        response.json()["error"] == "ERROR_AUTOMATIC_SNAPSHOT_SCHEDULE_ALREADY_EXISTS"
    )

    response = api_client.patch(
        workspace_url(workspace), {"hour": 3}, format="json", **auth
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["hour"] == 3

    response = api_client.delete(workspace_url(workspace), **auth)
    assert response.status_code == HTTP_204_NO_CONTENT

    assert list(
        AuditLogEntry.objects.filter(workspace_id=workspace.id)
        .order_by("id")
        .values_list("action_type", flat=True)
    ) == [
        "create_workspace_automatic_snapshot_schedule",
        "update_workspace_automatic_snapshot_schedule",
        "delete_workspace_automatic_snapshot_schedule",
    ]


@pytest.mark.django_db
def test_interval_too_short_is_refused(api_client, enterprise_data_fixture):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    database = enterprise_data_fixture.create_database_application(workspace=workspace)

    response = api_client.post(
        application_url(database),
        {"interval": "MINUTE", "minute": 15},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert (
        response.json()["error"]
        == "ERROR_AUTOMATIC_SNAPSHOT_SCHEDULE_INTERVAL_TOO_SHORT"
    )


@pytest.mark.django_db
def test_workspace_listing_returns_the_schedules(api_client, enterprise_data_fixture):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    enterprise_data_fixture.create_database_application(workspace=workspace, order=1)
    own = enterprise_data_fixture.create_database_application(
        workspace=workspace, order=2
    )
    off = enterprise_data_fixture.create_database_application(
        workspace=workspace, order=3
    )
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    api_client.post(application_url(own), DAILY, format="json", **auth)
    api_client.post(
        application_url(off), {**DAILY, "enabled": False}, format="json", **auth
    )

    response = api_client.get(workspace_url(workspace), **auth)

    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["workspace_default"] is None
    assert data["min_interval_minutes"] == 60
    # The application without a schedule of its own isn't listed: it follows the
    # workspace default.
    assert [
        (schedule["application_id"], schedule["enabled"])
        for schedule in data["application_schedules"]
    ] == [(own.id, True), (off.id, False)]


@pytest.mark.django_db
def test_bulk_apply_and_reset(api_client, enterprise_data_fixture):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    first = enterprise_data_fixture.create_database_application(workspace=workspace)
    second = enterprise_data_fixture.create_database_application(workspace=workspace)
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    api_client.post(
        application_url(second), {**DAILY, "enabled": False}, format="json", **auth
    )

    response = api_client.post(
        bulk_url(workspace),
        {
            "application_ids": [first.id, second.id],
            "action": "apply",
            "schedule": {**DAILY, "hour": 4},
        },
        format="json",
        **auth,
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    schedules = AutomaticSnapshotSchedule.objects.order_by("application_id")
    assert [(s.application_id, s.enabled, s.hour) for s in schedules] == [
        (first.id, True, 4),
        (second.id, True, 4),
    ]

    response = api_client.post(
        bulk_url(workspace),
        {"application_ids": [first.id, second.id], "action": "reset"},
        format="json",
        **auth,
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    assert not AutomaticSnapshotSchedule.objects.exists()


@pytest.mark.django_db
def test_application_admin_manages_only_their_application(
    api_client, enterprise_data_fixture
):
    admin = enterprise_data_fixture.create_user()
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(
        user=admin, custom_permissions=[(user, "EDITOR")]
    )
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    other = enterprise_data_fixture.create_database_application(workspace=workspace)
    RoleAssignmentHandler().assign_role(
        user, workspace, role=Role.objects.get(uid="ADMIN"), scope=database
    )
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    response = api_client.post(application_url(database), DAILY, format="json", **auth)
    assert response.status_code == HTTP_200_OK, response.json()

    # An application Admin can see the workspace default that covers their
    # application.
    response = api_client.get(application_url(database), **auth)
    assert response.status_code == HTTP_200_OK
    assert response.json()["state"] == "own_schedule"

    # An application Admin can turn their application off from the workspace
    # default.
    response = api_client.patch(
        application_url(database), {"enabled": False}, format="json", **auth
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.post(application_url(other), DAILY, format="json", **auth)
    assert response.status_code == HTTP_401_UNAUTHORIZED

    # The workspace default needs Admin as the workspace-level role.
    response = api_client.post(workspace_url(workspace), DAILY, format="json", **auth)
    assert response.status_code == HTTP_401_UNAUTHORIZED
    response = api_client.get(workspace_url(workspace), **auth)
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_workspace_editor_cannot_manage_schedules(api_client, enterprise_data_fixture):
    admin = enterprise_data_fixture.create_user()
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(
        user=admin, custom_permissions=[(user, "EDITOR")]
    )
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    response = api_client.post(application_url(database), DAILY, format="json", **auth)
    assert response.status_code == HTTP_401_UNAUTHORIZED

    response = api_client.post(workspace_url(workspace), DAILY, format="json", **auth)
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_schedules_need_the_license(api_client, enterprise_data_fixture):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    enterprise_data_fixture.delete_all_licenses()
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    response = api_client.post(application_url(database), DAILY, format="json", **auth)
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED

    response = api_client.get(workspace_url(workspace), **auth)
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
def test_bulk_checks_every_application(api_client, enterprise_data_fixture):
    admin = enterprise_data_fixture.create_user()
    editor, editor_token = enterprise_data_fixture.create_user_and_token()
    outsider, outsider_token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(
        user=admin, custom_permissions=[(editor, "EDITOR")]
    )
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    payload = {"application_ids": [database.id], "action": "reset"}

    response = api_client.post(
        bulk_url(workspace),
        payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {outsider_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    # Resetting an application without a schedule still needs the permission.
    response = api_client.post(
        bulk_url(workspace),
        payload,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {editor_token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_bulk_refuses_applications_outside_the_workspace(
    api_client, enterprise_data_fixture
):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    other_database = enterprise_data_fixture.create_database_application(user=user)

    response = api_client.post(
        bulk_url(workspace),
        {"application_ids": [other_database.id], "action": "reset"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_workspace_listing_only_returns_visible_applications(
    api_client, enterprise_data_fixture, mocker
):
    user, token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    visible = enterprise_data_fixture.create_database_application(workspace=workspace)
    hidden = enterprise_data_fixture.create_database_application(workspace=workspace)
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    api_client.post(workspace_url(workspace), DAILY, format="json", **auth)
    api_client.post(application_url(visible), DAILY, format="json", **auth)
    api_client.post(application_url(hidden), DAILY, format="json", **auth)

    from baserow.core.handler import CoreHandler

    filter_queryset = CoreHandler.filter_queryset

    def hide_application(self, actor, operation_name, queryset, workspace=None):
        queryset = filter_queryset(self, actor, operation_name, queryset, workspace)
        return queryset.exclude(id=hidden.id)

    mocker.patch.object(CoreHandler, "filter_queryset", hide_application)

    response = api_client.get(workspace_url(workspace), **auth)

    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["workspace_default"] is not None
    assert [s["application_id"] for s in data["application_schedules"]] == [visible.id]


@pytest.mark.django_db
def test_schedules_are_admin_only_without_roles(
    api_client, enterprise_data_fixture, mocker
):
    mocker.patch(
        "baserow_enterprise.role.permission_manager.RolePermissionManagerType"
        ".is_enabled",
        return_value=False,
    )
    admin, admin_token = enterprise_data_fixture.create_user_and_token()
    member, member_token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(
        user=admin, custom_permissions=[(member, "MEMBER")]
    )
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    member_auth = {"HTTP_AUTHORIZATION": f"JWT {member_token}"}

    response = api_client.post(
        application_url(database), DAILY, format="json", **member_auth
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    response = api_client.post(
        workspace_url(workspace), DAILY, format="json", **member_auth
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    response = api_client.get(workspace_url(workspace), **member_auth)
    assert response.status_code == HTTP_401_UNAUTHORIZED

    response = api_client.post(
        workspace_url(workspace),
        DAILY,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
