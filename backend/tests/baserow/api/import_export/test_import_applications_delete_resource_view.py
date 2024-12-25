from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_delete_non_existing_resource(data_fixture, api_client, tmpdir):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.delete(
        reverse(
            "api:workspaces:import_workspace_resource",
            kwargs={"workspace_id": workspace.id, "resource_id": 999999},
        ),
        data={},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_RESOURCE_DOES_NOT_EXIST"


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_delete_resource_invalid_user(data_fixture, api_client, tmpdir):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    user2 = data_fixture.create_user()

    token2 = data_fixture.generate_token(user2)
    response = api_client.delete(
        reverse(
            "api:workspaces:import_workspace_resource",
            kwargs={"workspace_id": workspace.id, "resource_id": 1},
        ),
        data={},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_deleting_valid_resource_marks_it_for_deleting(
    data_fixture, api_client, tmpdir, use_tmp_media_root
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    resource = data_fixture.create_import_export_resource(created_by=user)

    response = api_client.delete(
        reverse(
            "api:workspaces:import_workspace_resource",
            kwargs={"workspace_id": workspace.id, "resource_id": resource.id},
        ),
        data={},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    resource.refresh_from_db()
    assert resource.marked_for_deletion is True
