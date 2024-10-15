import os
from uuid import uuid4

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.utils import override_settings
from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)


@pytest.mark.import_workspace
@pytest.mark.django_db
@override_settings(
    FEATURE_FLAGS="",
)
def test_delete_resource_with_feature_flag_disabled(data_fixture, api_client, tmpdir):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.delete(
        reverse(
            "api:workspaces:import_workspace_delete_resource",
            kwargs={"workspace_id": workspace.id, "resource_id": str(uuid4())},
        ),
        data={},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN
    assert response.json()["error"] == "ERROR_FEATURE_DISABLED"


@pytest.mark.import_workspace
@pytest.mark.django_db
def test_delete_resource_from_non_existing_resource(data_fixture, api_client, tmpdir):
    user, token = data_fixture.create_user_and_token()

    response = api_client.delete(
        reverse(
            "api:workspaces:import_workspace_delete_resource",
            kwargs={"workspace_id": 999999, "resource_id": str(uuid4())},
        ),
        data={},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"


@pytest.mark.import_workspace
@pytest.mark.django_db
def test_delete_non_existing_resource(data_fixture, api_client, tmpdir):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.delete(
        reverse(
            "api:workspaces:import_workspace_delete_resource",
            kwargs={"workspace_id": workspace.id, "resource_id": str(uuid4())},
        ),
        data={},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_RESOURCE_DOES_NOT_EXIST"


@pytest.mark.import_workspace
@pytest.mark.django_db
def test_delete_resource_invalid_user(data_fixture, api_client, tmpdir):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    user2 = data_fixture.create_user()

    token2 = data_fixture.generate_token(user2)
    response = api_client.delete(
        reverse(
            "api:workspaces:import_workspace_delete_resource",
            kwargs={"workspace_id": workspace.id, "resource_id": str(uuid4())},
        ),
        data={},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.import_workspace
@pytest.mark.django_db
def test_delete_valid_resource(data_fixture, api_client, tmpdir, use_tmp_media_root):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    sources_path = os.path.join(
        settings.BASE_DIR, "../../../tests/baserow/api/import_export/sources"
    )

    with open(f"{sources_path}/interesting_database_export.zip", "rb") as export_file:
        file_content = export_file.read()

    uploaded_file = SimpleUploadedFile(
        "interesting_database_export.zip", file_content, content_type="application/zip"
    )

    response = api_client.post(
        reverse(
            "api:workspaces:import_workspace_upload_file",
            kwargs={
                "workspace_id": workspace.id,
            },
        ),
        data={
            "workspace_id": workspace.id,
            "file": uploaded_file,
        },
        format="multipart",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    resource_id = response.json()["id"]

    response = api_client.delete(
        reverse(
            "api:workspaces:import_workspace_delete_resource",
            kwargs={"workspace_id": workspace.id, "resource_id": resource_id},
        ),
        data={},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
