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
def test_create_snapshot_limit_reached(api_client, data_fixture, settings):
    settings.BASEROW_MAX_SNAPSHOTS_PER_GROUP = 3
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace(user=user)
    # workspace 1
    application_1 = data_fixture.create_database_application(
        workspace=workspace_1, order=1
    )
    application_2 = data_fixture.create_database_application(
        workspace=workspace_1, order=2
    )
    snapshot_1 = data_fixture.create_snapshot(
        user=user,
        snapshot_from_application=application_1,
        created_by=user,
        name="Snapshot1",
    )
    snapshot_2 = data_fixture.create_snapshot(
        user=user,
        snapshot_from_application=application_1,
        created_by=user,
        name="Snapshot2",
    )
    snapshot_3 = data_fixture.create_snapshot(
        user=user,
        snapshot_from_application=application_2,
        created_by=user,
        name="Snapshot3",
    )
    # workspace 2
    application_3 = data_fixture.create_database_application(
        workspace=workspace_2, order=1
    )
    snapshot_4 = data_fixture.create_snapshot(
        user=user,
        snapshot_from_application=application_3,
        created_by=user,
        name="Snapshot1",
    )

    response = api_client.post(
        reverse("api:snapshots:list", kwargs={"application_id": application_2.id}),
        {
            "name": "New snapshot",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_MAXIMUM_SNAPSHOTS_REACHED"

    response = api_client.post(
        reverse("api:snapshots:list", kwargs={"application_id": application_3.id}),
        {"name": "New snapshot"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_202_ACCEPTED


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
            "id": snapshot_2.id,
            "name": "Snapshot2",
        },
        {
            "snapshot_from_application": application_1.id,
            "created_at": "2021-01-02T12:00:00Z",
            "created_by": {"username": user.username},
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
