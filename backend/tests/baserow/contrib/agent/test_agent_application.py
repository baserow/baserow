from django.urls import reverse

import pytest

from baserow.contrib.agent.models import AgentApplication
from baserow.core.exceptions import FeatureDisabledException
from baserow.core.handler import CoreHandler
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.registries import ImportExportConfig
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.storage import get_default_storage
from baserow.core.utils import Progress


def duplicate(data_fixture, user, agent):
    return CoreHandler().duplicate_application(user, agent)


def restore_snapshot(data_fixture, user, agent):
    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=agent, name=agent.name, created_by=user
    )
    SnapshotHandler().perform_create(snapshot, Progress(total=100))
    return SnapshotHandler().perform_restore(snapshot, Progress(total=100))


def import_workspace_archive(data_fixture, user, agent):
    data_fixture.create_import_export_trusted_source()
    handler = ImportExportHandler()
    export = handler.export_workspace_applications(
        [agent],
        ImportExportConfig(
            include_permission_data=False, reduce_disk_space_usage=False
        ),
    )
    archive_path = handler.get_export_storage_path(export.get_archive_name())
    with get_default_storage().open(archive_path, "rb") as archive:
        resource = handler.create_resource_from_file(user, "agent.zip", archive)
    workspace = data_fixture.create_workspace(user=user)
    [imported] = handler.import_workspace_applications(user, workspace, resource)
    return imported


@pytest.mark.django_db
def test_agent_creation_requires_feature_flag(data_fixture, settings):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    settings.FEATURE_FLAGS = []

    with pytest.raises(FeatureDisabledException):
        CoreHandler().create_application(user, workspace, "agent", name="Agent")

    assert not AgentApplication.objects.exists()


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "copy_agent", [duplicate, restore_snapshot, import_workspace_archive]
)
def test_agent_copy_is_a_new_agent(data_fixture, use_tmp_media_root, copy_agent):
    user = data_fixture.create_user()
    agent = data_fixture.create_agent_application(user=user)

    copied = copy_agent(data_fixture, user, agent).specific

    assert isinstance(copied, AgentApplication)
    assert copied.id != agent.id
    assert AgentApplication.objects.filter(id=agent.id).exists()


@pytest.mark.django_db
@pytest.mark.workspace_search
def test_workspace_search_finds_agents(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    agent = data_fixture.create_agent_application(user=user, name="Researcher")

    response = api_client.get(
        reverse(
            "api:search:workspace_search",
            kwargs={"workspace_id": agent.workspace_id},
        ),
        {"query": "Research"},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 200
    [result] = response.json()["results"]
    assert (result["id"], result["type"], result["subtitle"]) == (
        agent.id,
        "agent",
        "Agents",
    )
