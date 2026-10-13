import json
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

import pytest

from baserow.core.handler import CoreHandler
from baserow.core.import_export.handler import MANIFEST_NAME, ImportExportHandler
from baserow.core.models import ExportApplicationsJob
from baserow.core.storage import get_default_storage
from baserow_enterprise.agent.models import AgentApplication


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_agent_archive_round_trip_uses_independent_application_ids(
    enterprise_data_fixture,
    api_client,
    use_tmp_media_root,
    django_capture_on_commit_callbacks,
):
    user, token = enterprise_data_fixture.create_user_and_token()
    source = enterprise_data_fixture.create_workspace(user=user)
    destination = enterprise_data_fixture.create_workspace(user=user)
    agents = [
        enterprise_data_fixture.create_agent_application(
            workspace=source, name=name, order=order
        )
        for order, name in enumerate(["Researcher", "Writer"], start=1)
    ]
    enterprise_data_fixture.create_import_export_trusted_source()
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(
            reverse(
                "api:workspaces:export_workspace_async",
                kwargs={"workspace_id": source.id},
            ),
            {"application_ids": [agent.id for agent in agents]},
            format="json",
            **headers,
        )
    assert response.status_code == 202, response.json()
    export_job = ExportApplicationsJob.objects.get(id=response.json()["id"])
    assert export_job.state == "finished", export_job.human_readable_error
    archive_path = ImportExportHandler().get_export_storage_path(
        export_job.resource.get_archive_name()
    )
    with get_default_storage().open(archive_path, "rb") as archive:
        archive_content = archive.read()
        archive.seek(0)
        with zipfile.ZipFile(archive) as zip_file:
            manifest = json.loads(zip_file.read(MANIFEST_NAME))
    assert [item["id"] for item in manifest["applications"]["agent"]["items"]] == [
        agent.id for agent in agents
    ]

    response = api_client.post(
        reverse(
            "api:workspaces:import_workspace_upload_file",
            kwargs={"workspace_id": destination.id},
        ),
        {
            "file": SimpleUploadedFile(
                "agents.zip", archive_content, content_type="application/zip"
            )
        },
        format="multipart",
        **headers,
    )
    assert response.status_code == 200, response.json()
    resource_id = response.json()["id"]

    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(
            reverse(
                "api:workspaces:import_workspace_async",
                kwargs={"workspace_id": destination.id},
            ),
            {"resource_id": resource_id},
            format="json",
            **headers,
        )
    assert response.status_code == 202, response.json()
    response = api_client.get(
        reverse("api:jobs:item", kwargs={"job_id": response.json()["id"]}), **headers
    )
    assert response.status_code == 200, response.json()
    imported = AgentApplication.objects.filter(workspace=destination).order_by("order")

    assert response.json()["state"] == "finished", response.json()
    imported = list(imported)
    assert [agent.name for agent in imported] == ["Researcher", "Writer"]
    assert {agent.id for agent in imported}.isdisjoint(agent.id for agent in agents)
    assert {item["id"] for item in response.json()["installed_applications"]} == {
        agent.id for agent in imported
    }
    CoreHandler().update_application(user, imported[0], name="Independent copy")
    CoreHandler().delete_application(user, imported[1])

    assert list(
        AgentApplication.objects.filter(workspace=source)
        .order_by("order")
        .values_list("name", flat=True)
    ) == ["Researcher", "Writer"]
