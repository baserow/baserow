import os

from django.conf import settings
from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_import_applications_into_non_existing_workspace(
    data_fixture, api_client, tmpdir
):
    user, token = data_fixture.create_user_and_token()

    response = api_client.post(
        reverse(
            "api:workspaces:import_workspace_async",
            kwargs={"workspace_id": 999999},
        ),
        data={
            "resource_id": 1,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"


@pytest.mark.import_export_workspace
@pytest.mark.django_db
def test_import_applications_from_non_existing_resource(
    data_fixture, api_client, tmpdir
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.post(
        reverse(
            "api:workspaces:import_workspace_async",
            kwargs={"workspace_id": workspace.id},
        ),
        data={"resource_id": 999999},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_RESOURCE_DOES_NOT_EXIST"


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_applications_with_non_existing_file(
    data_fixture, api_client, tmpdir, use_tmp_media_root
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    resource = data_fixture.create_import_export_resource(
        created_by=user, original_name="interesting_database.zip", is_valid=False
    )

    response = api_client.post(
        reverse(
            "api:workspaces:import_workspace_async",
            kwargs={"workspace_id": workspace.id},
        ),
        data={"resource_id": resource.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_RESOURCE_IS_INVALID"


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_applications(data_fixture, api_client, tmpdir, use_tmp_media_root):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    sources_path = os.path.join(
        settings.BASE_DIR, "../../../tests/baserow/api/import_export/sources"
    )

    data_fixture.create_import_export_trusted_source()

    resource = data_fixture.create_import_export_resource(
        created_by=user, original_name="interesting_database.zip", is_valid=True
    )

    with open(f"{sources_path}/interesting_database_export.zip", "rb") as export_file:
        content = export_file.read()
        data_fixture.create_import_export_resource_file(
            resource=resource, content=content
        )

    response = api_client.post(
        reverse(
            "api:workspaces:import_workspace_async",
            kwargs={"workspace_id": workspace.id},
        ),
        data={"resource_id": resource.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_202_ACCEPTED
    job_id = response.json()["id"]

    token = data_fixture.generate_token(user)
    response = api_client.get(
        reverse("api:jobs:item", kwargs={"job_id": job_id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["state"] == "finished"
    assert response_json["progress_percentage"] == 100
    assert len(response_json["installed_applications"]) > 0


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_specific_application_ids(
    data_fixture, api_client, tmpdir, use_tmp_media_root
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    sources_path = os.path.join(
        settings.BASE_DIR, "../../../tests/baserow/api/import_export/sources"
    )

    data_fixture.disable_import_signature_verification()

    resource = data_fixture.create_import_export_resource(
        created_by=user, original_name="multiple_applications_export.zip", is_valid=True
    )

    with open(f"{sources_path}/multiple_applications_export.zip", "rb") as export_file:
        content = export_file.read()
        data_fixture.create_import_export_resource_file(
            resource=resource, content=content
        )

        response = api_client.post(
            reverse(
                "api:workspaces:import_workspace_async",
                kwargs={"workspace_id": workspace.id},
            ),
            data={
                "resource_id": resource.id,
                "application_ids": [2],
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_202_ACCEPTED
    job_id = response.json()["id"]

    response = api_client.get(
        reverse("api:jobs:item", kwargs={"job_id": job_id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["state"] == "finished"
    assert response_json["progress_percentage"] == 100
    assert response_json["installed_applications"] is not None
    installed_applications = response_json["installed_applications"]
    assert len(installed_applications) == 1
    assert installed_applications[0]["name"] == "Database 2"


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_without_application_ids(
    data_fixture, api_client, tmpdir, use_tmp_media_root
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    sources_path = os.path.join(
        settings.BASE_DIR, "../../../tests/baserow/api/import_export/sources"
    )

    data_fixture.disable_import_signature_verification()

    resource = data_fixture.create_import_export_resource(
        created_by=user, original_name="multiple_applications_export.zip", is_valid=True
    )

    with open(f"{sources_path}/multiple_applications_export.zip", "rb") as export_file:
        content = export_file.read()
        data_fixture.create_import_export_resource_file(
            resource=resource, content=content
        )

        response = api_client.post(
            reverse(
                "api:workspaces:import_workspace_async",
                kwargs={"workspace_id": workspace.id},
            ),
            data={
                "resource_id": resource.id,
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_202_ACCEPTED
    job_id = response.json()["id"]

    response = api_client.get(
        reverse("api:jobs:item", kwargs={"job_id": job_id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["state"] == "finished"
    assert response_json["progress_percentage"] == 100
    assert response_json["installed_applications"] is not None
    installed_applications = response_json["installed_applications"]
    assert len(installed_applications) == 2
    assert installed_applications[0]["name"] == "Database 1"
    assert installed_applications[1]["name"] == "Database 2"


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_import_with_nonexistent_application_ids(
    data_fixture, api_client, tmpdir, use_tmp_media_root
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    sources_path = os.path.join(
        settings.BASE_DIR, "../../../tests/baserow/api/import_export/sources"
    )

    data_fixture.disable_import_signature_verification()

    resource = data_fixture.create_import_export_resource(
        created_by=user, original_name="multiple_applications_export.zip", is_valid=True
    )

    with open(f"{sources_path}/multiple_applications_export.zip", "rb") as export_file:
        content = export_file.read()
        data_fixture.create_import_export_resource_file(
            resource=resource, content=content
        )

        response = api_client.post(
            reverse(
                "api:workspaces:import_workspace_async",
                kwargs={"workspace_id": workspace.id},
            ),
            data={
                "resource_id": resource.id,
                "application_ids": [1, 999999],
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_202_ACCEPTED
    job_id = response.json()["id"]

    response = api_client.get(
        reverse("api:jobs:item", kwargs={"job_id": job_id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()

    assert response.status_code == HTTP_200_OK
    assert response_json["state"] == "failed"
    assert response_json["human_readable_error"] == (
        "One or more of the specified application IDs were not"
        " found in the export file."
    )
