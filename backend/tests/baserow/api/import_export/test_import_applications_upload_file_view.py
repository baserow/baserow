import os

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_upload_file_into_non_existing_workspace(data_fixture, api_client, tmpdir):
    user, token = data_fixture.create_user_and_token()

    response = api_client.post(
        reverse(
            "api:workspaces:import_workspace_upload_file",
            kwargs={"workspace_id": 999999},
        ),
        data={},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_upload_file_invalid_user(data_fixture, api_client, tmpdir):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    user2 = data_fixture.create_user()

    token2 = data_fixture.generate_token(user2)
    response = api_client.post(
        reverse(
            "api:workspaces:import_workspace_upload_file",
            kwargs={"workspace_id": workspace.id},
        ),
        data={},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_upload_file_without_attachment(data_fixture, api_client, tmpdir):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.post(
        reverse(
            "api:workspaces:import_workspace_upload_file",
            kwargs={"workspace_id": workspace.id},
        ),
        data={},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_FILE"


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_upload_file_not_zip(data_fixture, api_client, tmpdir):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    uploaded_file = SimpleUploadedFile(
        "broken_file.zip", b"Test file content", content_type="application/zip"
    )

    response = api_client.post(
        reverse(
            "api:workspaces:import_workspace_upload_file",
            kwargs={
                "workspace_id": workspace.id,
            },
        ),
        data={
            "file": uploaded_file,
        },
        format="multipart",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_FILE"


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_upload_valid_file(data_fixture, api_client, tmpdir, use_tmp_media_root):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    sources_path = os.path.join(
        settings.BASE_DIR, "../../../tests/baserow/api/import_export/sources"
    )

    with open(f"{sources_path}/interesting_database_export.zip", "rb") as export_file:
        file_content = export_file.read()

    data_fixture.create_import_export_trusted_source()

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
            "file": uploaded_file,
        },
        format="multipart",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert "id" in response.json()
