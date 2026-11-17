from unittest.mock import patch

from django.shortcuts import reverse

import pytest
from freezegun import freeze_time
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.core.jobs.constants import JOB_STARTED
from baserow.core.jobs.models import JOB_STATES_RUNNING
from baserow.test_utils.helpers import is_dict_subset

# Create


@pytest.mark.django_db
@pytest.mark.parametrize("token_header", ["JWT invalid", "Token invalid"])
def test_create_snapshot_invalid_token(api_client, data_fixture, token_header):
    user, jwt_token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    url = reverse("api:snapshots:list", kwargs={"application_id": application_1.id})

    response = api_client.post(
        url,
        {"name": "Test snapshot"},
        format="json",
        HTTP_AUTHORIZATION=token_header,
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_create_snapshot_user_not_in_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_not_in_workspace, token_not_in_workspace = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    url = reverse("api:snapshots:list", kwargs={"application_id": application_1.id})

    response = api_client.post(
        url,
        {"name": "Test snapshot"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_not_in_workspace}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_create_snapshot_app_not_found(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    snapshot_name = "Test snapshot name"
    url = reverse("api:snapshots:list", kwargs={"application_id": "1234"})

    response = api_client.post(
        url,
        {"name": snapshot_name},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_create_snapshot_body_validation(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    url = reverse("api:snapshots:list", kwargs={"application_id": application_1.id})

    response = api_client.post(
        url, {}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_create_snapshot(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_1.snapshot_default_keep = 1
    workspace_1.save()
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    url = reverse("api:snapshots:list", kwargs={"application_id": application_1.id})
    snapshot_name = "Test snapshot name"

    response = api_client.post(
        url,
        {"name": snapshot_name},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_202_ACCEPTED
    assert is_dict_subset(
        {
            "human_readable_error": "",
            "progress_percentage": 0,
            "state": "pending",
            "type": "create_snapshot",
        },
        response.json(),
    )


@pytest.mark.django_db
def test_create_snapshot_without_room(api_client, data_fixture, settings):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    no_keep = data_fixture.create_database_application(workspace=workspace)
    full = data_fixture.create_database_application(workspace=workspace)
    full.snapshot_keep = 1
    full.save()
    data_fixture.create_snapshot(user=user, snapshot_from_application=full)

    def create(application):
        return api_client.post(
            reverse("api:snapshots:list", kwargs={"application_id": application.id}),
            {"name": "New snapshot"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    response = create(no_keep)
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_SNAPSHOT_KEEP_IS_ZERO"

    response = create(full)
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_SNAPSHOT_KEEP_FULL_OF_PROTECTED"

    settings.BASEROW_MAX_SNAPSHOTS_PER_GROUP = 0
    response = create(full)
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_MAXIMUM_SNAPSHOTS_REACHED"


# List


@pytest.mark.django_db
@pytest.mark.parametrize("token_header", ["JWT invalid", "Token invalid"])
def test_list_snapshots_invalid_token(api_client, data_fixture, token_header):
    user, jwt_token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    url = reverse("api:snapshots:list", kwargs={"application_id": application_1.id})

    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=token_header,
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_list_snapshots_user_not_in_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_not_in_workspace, token_not_in_workspace = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    url = reverse("api:snapshots:list", kwargs={"application_id": application_1.id})

    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_not_in_workspace}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_list_snapshots_app_not_found(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    response = api_client.get(
        reverse("api:snapshots:list", kwargs={"application_id": "1234"}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_list_snapshots(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user2, token2 = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    application_2 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    fake_snapshot_app = data_fixture.create_database_application(
        workspace=workspace_1, order=3
    )
    with freeze_time("2021-01-02 12:00"):
        snapshot_1 = data_fixture.create_snapshot(
            user=user,
            snapshot_from_application=application_1,
            created_by=user,
            name="Snapshot1",
            snapshot_to_application=fake_snapshot_app,
        )
        snapshot_2 = data_fixture.create_snapshot(
            user=user,
            snapshot_from_application=application_1,
            created_by=user2,
            name="Snapshot2",
            snapshot_to_application=fake_snapshot_app,
        )
        snapshot_3 = data_fixture.create_snapshot(
            user=user,
            snapshot_from_application=application_2,
            created_by=user2,
            name="Snapshot3",
            snapshot_to_application=fake_snapshot_app,
        )
    url = reverse("api:snapshots:list", kwargs={"application_id": application_1.id})

    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == [
        {
            "snapshot_from_application": application_1.id,
            "created_at": "2021-01-02T12:00:00Z",
            "created_by": {"username": user2.username},
            "created_automatically": False,
            "protected": True,
            "id": snapshot_2.id,
            "name": "Snapshot2",
        },
        {
            "snapshot_from_application": application_1.id,
            "created_at": "2021-01-02T12:00:00Z",
            "created_by": {"username": user.username},
            "created_automatically": False,
            "protected": True,
            "id": snapshot_1.id,
            "name": "Snapshot1",
        },
    ]


# Restore


@pytest.mark.django_db
@pytest.mark.parametrize("token_header", ["JWT invalid", "Token invalid"])
def test_restore_snapshot_invalid_token(api_client, data_fixture, token_header):
    user, jwt_token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    snapshot_1 = data_fixture.create_snapshot(
        user=user,
        snapshot_from_application=application_1,
        created_by=user,
        name="Snapshot1",
    )
    url = reverse("api:snapshots:restore", kwargs={"snapshot_id": snapshot_1.id})

    response = api_client.post(
        url,
        format="json",
        HTTP_AUTHORIZATION=token_header,
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_restore_snapshot_user_not_in_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_not_in_workspace, token_not_in_workspace = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    snapshot_1 = data_fixture.create_snapshot(
        user=user,
        snapshot_from_application=application_1,
        created_by=user,
        name="Snapshot1",
    )
    url = reverse("api:snapshots:restore", kwargs={"snapshot_id": snapshot_1.id})

    response = api_client.post(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_not_in_workspace}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_restore_snapshot_not_found(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    response = api_client.post(
        reverse("api:snapshots:restore", kwargs={"snapshot_id": 1234}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_restore_snapshot(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    snapshot_1 = data_fixture.create_snapshot(
        user=user,
        snapshot_from_application=application_1,
        created_by=user,
        name="Snapshot1",
    )
    url = reverse("api:snapshots:restore", kwargs={"snapshot_id": snapshot_1.id})

    response = api_client.post(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert is_dict_subset(
        {
            "human_readable_error": "",
            "progress_percentage": 0,
            "state": "pending",
            "type": "restore_snapshot",
        },
        response.json(),
    )


# Delete


@pytest.mark.django_db
@pytest.mark.parametrize("token_header", ["JWT invalid", "Token invalid"])
def test_delete_snapshot_invalid_token(api_client, data_fixture, token_header):
    user, jwt_token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    snapshot_1 = data_fixture.create_snapshot(
        user=user,
        snapshot_from_application=application_1,
        created_by=user,
        name="Snapshot1",
    )
    url = reverse("api:snapshots:item", kwargs={"snapshot_id": snapshot_1.id})

    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=token_header,
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_delete_snapshot_user_not_in_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    user_not_in_workspace, token_not_in_workspace = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    snapshot_1 = data_fixture.create_snapshot(
        user=user,
        snapshot_from_application=application_1,
        created_by=user,
        name="Snapshot1",
    )
    url = reverse("api:snapshots:item", kwargs={"snapshot_id": snapshot_1.id})

    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_not_in_workspace}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_delete_snapshot_not_found(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    response = api_client.delete(
        reverse("api:snapshots:item", kwargs={"snapshot_id": 1234}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db(transaction=True)
def test_delete_snapshot(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    snapshot_1 = data_fixture.create_snapshot(
        user=user,
        snapshot_from_application=application_1,
        created_by=user,
        name="Snapshot1",
    )
    url = reverse("api:snapshots:item", kwargs={"snapshot_id": snapshot_1.id})

    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db(transaction=True)
def test_get_current_snapshot_job(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_1.snapshot_default_keep = 1
    workspace_1.save()
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )

    url = reverse("api:snapshots:list", kwargs={"application_id": application_1.id})
    snapshot_name = "Test snapshot name"

    with patch("baserow.core.jobs.tasks.run_async_job.delay"):
        response = api_client.post(
            url,
            {"name": snapshot_name},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

        assert response.status_code == HTTP_202_ACCEPTED
        assert is_dict_subset(
            {
                "human_readable_error": "",
                "progress_percentage": 0,
                "state": "pending",
                "type": "create_snapshot",
            },
            response.json(),
        )

    url = reverse("api:jobs:list")

    response = api_client.get(
        url,
        {"state": JOB_STARTED},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    resp = response.json()
    assert isinstance(resp, dict)
    assert "jobs" in resp
    resp = resp["jobs"]
    assert isinstance(resp, list)
    assert len(resp) == 1
    assert isinstance(resp[0], dict)
    assert is_dict_subset(
        {
            "snapshot": {
                "name": "Test snapshot name",
            }
        },
        resp[0],
    )


@pytest.mark.django_db(transaction=True)
def test_get_current_snapshot_job_cancelled(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_1.snapshot_default_keep = 1
    workspace_1.save()
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )

    url = reverse("api:snapshots:list", kwargs={"application_id": application_1.id})
    snapshot_name = "Test snapshot name"

    with patch("baserow.core.jobs.tasks.run_async_job.delay"):
        response = api_client.post(
            url,
            {"name": snapshot_name},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

        assert response.status_code == HTTP_202_ACCEPTED
        assert is_dict_subset(
            {
                "human_readable_error": "",
                "progress_percentage": 0,
                "state": "pending",
                "type": "create_snapshot",
            },
            response.json(),
        )

    # list jobs to match with a snapshot
    url = reverse("api:jobs:list")
    response = api_client.get(
        url,
        {"state": JOB_STATES_RUNNING},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    resp = response.json()
    assert isinstance(resp, dict)
    assert "jobs" in resp
    resp = resp["jobs"]
    assert len(resp) == 1
    assert isinstance(resp[0], dict)

    assert isinstance(resp[0].get("snapshot"), dict)
    assert is_dict_subset({"name": snapshot_name}, resp[0].get("snapshot"))

    job_id = resp[0]["id"]

    url = reverse("api:jobs:cancel", kwargs={"job_id": job_id})

    response = api_client.post(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    url = reverse("api:snapshots:list", kwargs={"application_id": application_1.id})

    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    resp = response.json()
    assert resp == []


# Usage


@pytest.mark.django_db
def test_get_snapshot_usage(api_client, data_fixture, settings):
    settings.BASEROW_MAX_SNAPSHOTS_PER_GROUP = 5
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    other_application = data_fixture.create_database_application(workspace=workspace)
    workspace.snapshot_default_keep = 2
    workspace.save()
    application.snapshot_keep = 3
    application.save()
    data_fixture.create_snapshot(snapshot_from_application=application, user=user)
    data_fixture.create_snapshot(
        snapshot_from_application=application, user=user, protected=False
    )
    data_fixture.create_snapshot(snapshot_from_application=other_application, user=user)
    url = reverse("api:snapshots:usage", kwargs={"application_id": application.id})

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "used": 5,
        "limit": 5,
        "over_allowance": False,
        "blocked": False,
        "snapshot_count": 3,
        "default_keep": 2,
        "max_keep": None,
        "expiration_days": settings.BASEROW_SNAPSHOT_EXPIRATION_TIME_DAYS,
        "keep": 3,
        "effective_keep": 3,
        "application_snapshot_count": 2,
        "protected_count": 1,
    }


@pytest.mark.django_db
def test_get_snapshot_usage_without_limit(api_client, data_fixture, settings):
    settings.BASEROW_MAX_SNAPSHOTS_PER_GROUP = -1
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_database_application(user=user)
    url = reverse("api:snapshots:usage", kwargs={"application_id": application.id})

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.json()["limit"] is None


@pytest.mark.django_db
def test_get_snapshot_usage_outside_the_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_database_application()
    url = reverse("api:snapshots:usage", kwargs={"application_id": application.id})

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


# Keep and protection


@pytest.mark.django_db
def test_update_application_snapshot_keep(api_client, data_fixture, settings):
    settings.BASEROW_MAX_SNAPSHOTS_PER_GROUP = 4
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    url = reverse(
        "api:snapshots:application_keep", kwargs={"application_id": application.id}
    )

    response = api_client.patch(
        url, {"keep": 4}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["keep"] == 4
    assert response.json()["used"] == 4

    response = api_client.patch(
        url, {"keep": 5}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_SNAPSHOT_KEEP_EXCEEDS_ALLOWANCE"

    response = api_client.patch(
        url, {"keep": None}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["keep"] is None
    assert response.json()["effective_keep"] == 0

    response = api_client.patch(
        url, {"keep": -1}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_lower_application_snapshot_keep_needs_confirmation(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    application.snapshot_keep = 2
    application.save()
    data_fixture.create_snapshot(
        snapshot_from_application=application, user=user, protected=False
    )
    data_fixture.create_snapshot(
        snapshot_from_application=application, user=user, protected=False
    )
    url = reverse(
        "api:snapshots:application_keep", kwargs={"application_id": application.id}
    )

    with patch("baserow.core.snapshots.handler.delete_application_snapshot"):
        response = api_client.patch(
            url, {"keep": 1}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error": "ERROR_SNAPSHOT_KEEP_CHANGE_DELETES_SNAPSHOTS",
            "detail": "Lowering the keep deletes 1 snapshot(s). Send "
            "`delete_snapshots` to confirm.",
        }

        response = api_client.patch(
            url,
            {"keep": 1, "delete_snapshots": True},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK
    assert response.json()["application_snapshot_count"] == 1


@pytest.mark.django_db
def test_update_application_snapshot_keep_outside_the_workspace(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_database_application()
    url = reverse(
        "api:snapshots:application_keep", kwargs={"application_id": application.id}
    )

    response = api_client.patch(
        url, {"keep": 1}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_workspace_snapshot_settings(api_client, data_fixture, settings):
    settings.BASEROW_MAX_SNAPSHOTS_PER_GROUP = 10
    settings.BASEROW_MAX_SNAPSHOTS_KEEP_PER_APPLICATION = 3
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    url = reverse("api:snapshots:workspace", kwargs={"workspace_id": workspace.id})

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "used": 0,
        "limit": 10,
        "over_allowance": False,
        "blocked": False,
        "snapshot_count": 0,
        "default_keep": 0,
        "max_keep": 3,
        "expiration_days": settings.BASEROW_SNAPSHOT_EXPIRATION_TIME_DAYS,
        "applications": [
            {
                "id": application.id,
                "keep": None,
                "snapshot_count": 0,
                "protected_count": 0,
            }
        ],
    }

    response = api_client.patch(
        url, {"default_keep": 3}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["default_keep"] == 3
    assert response.json()["used"] == 3

    response = api_client.patch(
        url, {"default_keep": 4}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_SNAPSHOT_KEEP_ABOVE_MAXIMUM"


@pytest.mark.django_db
def test_update_workspace_snapshot_settings_needs_an_admin(api_client, data_fixture):
    admin = data_fixture.create_user()
    member, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    url = reverse("api:snapshots:workspace", kwargs={"workspace_id": workspace.id})

    response = api_client.patch(
        url, {"default_keep": 1}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_update_snapshot_protection(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    other_user, other_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_database_application(workspace=workspace)
    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=application, user=user
    )
    url = reverse("api:snapshots:item", kwargs={"snapshot_id": snapshot.id})

    response = api_client.patch(
        url, {"protected": False}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["protected"] is False
    snapshot.refresh_from_db()
    assert snapshot.protected is False

    response = api_client.patch(
        url,
        {"protected": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_update_application_snapshot_keep_too_large(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_database_application(user=user)
    url = reverse(
        "api:snapshots:application_keep", kwargs={"application_id": application.id}
    )

    response = api_client.patch(
        url, {"keep": 3000000000}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
