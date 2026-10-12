import json

import pytest

from baserow.core.exceptions import FeatureDisabledException
from baserow.core.handler import CoreHandler
from baserow.core.models import Application, TrashEntry
from baserow.core.registries import ImportExportConfig
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import Progress
from baserow_enterprise.agent.application_types import AgentApplicationType
from baserow_enterprise.agent.models import AgentApplication

from .test_api import application_url


@pytest.mark.django_db
def test_agent_export_import_preserves_application_and_remaps_id(
    enterprise_data_fixture,
):
    agent = enterprise_data_fixture.create_agent_application(name="Researcher", order=2)
    config = ImportExportConfig(include_permission_data=False)
    serialized = json.loads(
        json.dumps(AgentApplicationType().export_serialized(agent, config))
    )
    assert serialized == {
        "id": agent.id,
        "name": "Researcher",
        "order": 2,
        "type": "agent",
    }
    destination = enterprise_data_fixture.create_workspace()
    mapping = {}
    imported = AgentApplicationType().import_serialized(
        destination, serialized, config, mapping
    )
    assert isinstance(imported, AgentApplication)
    assert imported.id != agent.id
    assert imported.workspace == destination
    assert imported.name == agent.name
    assert imported.order == agent.order
    assert mapping["applications"] == {agent.id: imported.id}
    assert AgentApplication.objects.get(id=agent.id).workspace == agent.workspace


@pytest.mark.django_db
def test_duplicate_agent_creates_independent_application(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    agent = enterprise_data_fixture.create_agent_application(
        user=user, name="Researcher"
    )
    copied = CoreHandler().duplicate_application(user, agent).specific
    assert isinstance(copied, AgentApplication)
    assert copied.id != agent.id
    assert copied.workspace == agent.workspace
    CoreHandler().update_application(user, copied, name="Independent copy")
    agent.refresh_from_db()
    assert agent.name == "Researcher"
    CoreHandler().delete_application(user, copied)
    assert AgentApplication.objects.get(id=agent.id).name == "Researcher"


@pytest.mark.django_db
def test_snapshot_captures_and_restores_independent_agent(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    agent = enterprise_data_fixture.create_agent_application(
        user=user, name="Researcher"
    )
    snapshot = enterprise_data_fixture.create_snapshot(
        snapshot_from_application=agent, name="Agent snapshot", created_by=user
    )
    SnapshotHandler().perform_create(snapshot, Progress(total=100))
    snapshot.refresh_from_db()
    captured = snapshot.snapshot_to_application.specific
    assert isinstance(captured, AgentApplication)
    assert captured.workspace_id is None
    assert captured.id != agent.id
    assert captured.name == "Researcher"
    CoreHandler().update_application(user, agent, name="Changed after snapshot")

    restored = SnapshotHandler().perform_restore(snapshot, Progress(total=100)).specific
    assert isinstance(restored, AgentApplication)
    assert restored.id not in [agent.id, captured.id]
    assert restored.workspace_id == agent.workspace_id
    assert restored.name == snapshot.name
    agent.refresh_from_db()
    assert agent.name == "Changed after snapshot"


@pytest.mark.django_db
def test_agent_trash_restore_and_cleanup_preserve_other_agents(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    agent = enterprise_data_fixture.create_agent_application(
        user=user, name="Researcher"
    )
    other = enterprise_data_fixture.create_agent_application(workspace=agent.workspace)
    CoreHandler().delete_application(user, agent)
    assert not AgentApplication.objects.filter(id=agent.id).exists()
    entry = TrashEntry.objects.get(
        trash_item_type="application", trash_item_id=agent.id
    )
    assert entry.application_id == agent.id
    assert entry.workspace_id == agent.workspace_id
    assert AgentApplication.objects.filter(id=other.id).exists()

    restored = TrashHandler.restore_item(user, "application", agent.id)
    assert restored.id == agent.id
    assert AgentApplication.objects.get(id=agent.id).name == "Researcher"
    assert not TrashEntry.objects.filter(id=entry.id).exists()
    CoreHandler().delete_application(user, agent)
    TrashEntry.objects.filter(
        trash_item_type="application", trash_item_id=agent.id
    ).update(should_be_permanently_deleted=True)
    TrashHandler.permanently_delete_marked_trash()
    assert not Application.objects_and_trash.filter(id=agent.id).exists()
    assert not AgentApplication.objects_and_trash.filter(id=agent.id).exists()
    assert not TrashEntry.objects.filter(trash_item_id=agent.id).exists()
    assert AgentApplication.objects.filter(id=other.id).exists()


@pytest.mark.django_db
def test_agent_access_hidden_while_workspace_trashed(
    enterprise_data_fixture, api_client
):
    user, token = enterprise_data_fixture.create_user_and_token()
    agent = enterprise_data_fixture.create_agent_application(user=user)
    TrashHandler.trash(user, agent.workspace, None, agent.workspace)
    assert (
        api_client.get(
            application_url(agent), HTTP_AUTHORIZATION=f"JWT {token}"
        ).status_code
        == 404
    )
    TrashHandler.restore_item(user, "workspace", agent.workspace_id)
    assert (
        api_client.get(
            application_url(agent), HTTP_AUTHORIZATION=f"JWT {token}"
        ).status_code
        == 200
    )


@pytest.mark.django_db
def test_agent_import_disabled_by_feature_flag(enterprise_data_fixture, settings):
    workspace = enterprise_data_fixture.create_workspace()
    settings.FEATURE_FLAGS = []
    with pytest.raises(FeatureDisabledException):
        AgentApplicationType().import_serialized(
            workspace,
            {"id": 1, "name": "Researcher", "order": 1, "type": "agent"},
            ImportExportConfig(include_permission_data=False),
            {},
        )
    assert not AgentApplication.objects.exists()


@pytest.mark.django_db
def test_agent_restore_disabled_by_feature_flag(enterprise_data_fixture, settings):
    user = enterprise_data_fixture.create_user()
    agent = enterprise_data_fixture.create_agent_application(user=user)
    CoreHandler().delete_application(user, agent)
    settings.FEATURE_FLAGS = []
    with pytest.raises(FeatureDisabledException):
        TrashHandler.restore_item(user, "application", agent.id)
    assert TrashEntry.objects.filter(
        trash_item_type="application", trash_item_id=agent.id
    ).exists()
    assert AgentApplication.objects_and_trash.get(id=agent.id).trashed


@pytest.mark.django_db
def test_agent_permanent_cleanup_works_when_disabled(enterprise_data_fixture, settings):
    user = enterprise_data_fixture.create_user()
    agent = enterprise_data_fixture.create_agent_application(user=user)
    other = enterprise_data_fixture.create_agent_application(workspace=agent.workspace)
    CoreHandler().delete_application(user, agent)
    TrashEntry.objects.filter(
        trash_item_type="application", trash_item_id=agent.id
    ).update(should_be_permanently_deleted=True)
    settings.FEATURE_FLAGS = []
    TrashHandler.permanently_delete_marked_trash()
    assert not AgentApplication.objects_and_trash.filter(id=agent.id).exists()
    assert not Application.objects_and_trash.filter(id=agent.id).exists()
    assert not TrashEntry.objects.exists()
    assert AgentApplication.objects.filter(id=other.id).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("operation", ["list", "create", "restore"])
def test_agent_snapshots_disabled_by_feature_flag(
    enterprise_data_fixture, settings, operation
):
    user = enterprise_data_fixture.create_user()
    agent = enterprise_data_fixture.create_agent_application(user=user)
    handler = SnapshotHandler()
    snapshot = handler.create(agent.id, user, "Agent snapshot")
    handler.perform_create(snapshot, Progress(total=100))
    snapshot.refresh_from_db()
    settings.FEATURE_FLAGS = []
    with pytest.raises(FeatureDisabledException):
        if operation == "list":
            handler.list(agent.id, user)
        elif operation == "create":
            handler.create(agent.id, user, "Another snapshot")
        else:
            handler.start_restore_job(snapshot.id, user)
    assert AgentApplication.objects.filter(workspace=agent.workspace).count() == 1
