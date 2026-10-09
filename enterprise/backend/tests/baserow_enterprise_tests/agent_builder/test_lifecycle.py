import json
from zipfile import ZipFile

import pytest

from baserow.core.actions import ExportApplicationsActionType
from baserow.core.exceptions import FeatureDisabledException
from baserow.core.handler import CoreHandler
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.models import Application, Operation, TrashEntry
from baserow.core.registries import ImportExportConfig
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.snapshots.operations import (
    CreateSnapshotApplicationOperationType,
    RestoreApplicationSnapshotOperationType,
)
from baserow.core.storage import get_default_storage
from baserow.core.trash.exceptions import CannotRestoreChildBeforeParent
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import Progress
from baserow_enterprise.agent_builder.application_types import (
    AgentBuilderApplicationType,
)
from baserow_enterprise.agent_builder.models import AgentBuilder, AgentDefinition
from baserow_enterprise.agent_builder.service import AgentService
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.mark.django_db
def test_agent_builder_export_import_preserves_empty_agents_and_remaps_ids(
    enterprise_data_fixture,
):
    builder = enterprise_data_fixture.create_agent_builder_application(name="Team")
    second = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, name="Writer", order=2
    )
    first = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, name="Researcher", order=1
    )
    enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, name="Deleted", order=3, trashed=True
    )
    config = ImportExportConfig(include_permission_data=False)
    serialized = json.loads(
        json.dumps(AgentBuilderApplicationType().export_serialized(builder, config))
    )
    assert serialized["type"] == "agent_builder"
    assert [
        (agent["id"], agent["name"], agent["order"]) for agent in serialized["agents"]
    ] == [(first.id, "Researcher", 1), (second.id, "Writer", 2)]

    destination = enterprise_data_fixture.create_workspace()
    mapping = {}
    imported = AgentBuilderApplicationType().import_serialized(
        destination, serialized, config, mapping
    )
    assert imported.id != builder.id
    assert imported.workspace == destination
    assert imported.name == "Team"
    assert list(imported.agents.values_list("name", "order")) == [
        ("Researcher", 1),
        ("Writer", 2),
    ]
    assert set(imported.agents.values_list("id", flat=True)).isdisjoint(
        {first.id, second.id}
    )
    assert AgentDefinition.objects.filter(agent_builder=builder).count() == 2


@pytest.mark.django_db
def test_duplicate_agent_builder_clones_agents_without_sharing_definitions(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    builder = enterprise_data_fixture.create_agent_builder_application(user=user)
    source_agent = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, name="Researcher", order=2
    )
    clone = CoreHandler().duplicate_application(user, builder).specific
    assert clone.id != builder.id
    copied_agent = clone.agents.get()
    assert copied_agent.id != source_agent.id
    assert copied_agent.name == source_agent.name
    assert copied_agent.order == source_agent.order
    copied_agent.name = "Separate definition"
    copied_agent.save()
    source_agent.refresh_from_db()
    assert source_agent.name == "Researcher"


@pytest.mark.django_db
def test_snapshot_captures_and_restores_agent_definitions(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    builder = enterprise_data_fixture.create_agent_builder_application(user=user)
    agent = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, name="Researcher"
    )
    snapshot = enterprise_data_fixture.create_snapshot(
        snapshot_from_application=builder, name="Team snapshot", created_by=user
    )
    SnapshotHandler().perform_create(snapshot, Progress(total=100))
    snapshot.refresh_from_db()
    assert snapshot.snapshot_to_application.workspace_id is None
    copied = AgentDefinition.objects_and_trash.get(
        agent_builder_id=snapshot.snapshot_to_application_id
    )
    assert copied.name == "Researcher"
    assert copied.id != agent.id
    agent.name = "Changed after snapshot"
    agent.save()

    restored = SnapshotHandler().perform_restore(snapshot, Progress(total=100)).specific
    assert isinstance(restored, AgentBuilder)
    assert restored.id != builder.id
    assert restored.workspace_id == builder.workspace_id
    assert restored.agents.get().name == "Researcher"
    agent.refresh_from_db()
    assert agent.name == "Changed after snapshot"


@pytest.mark.django_db
def test_agent_trash_restore_and_permanent_cleanup(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    agent = enterprise_data_fixture.create_agent_definition(
        user=user, name="Researcher"
    )
    AgentService().delete_agent(user, agent.id)
    assert not AgentDefinition.objects.filter(id=agent.id).exists()
    entry = TrashEntry.objects.get(
        trash_item_type="agent_builder_agent", trash_item_id=agent.id
    )
    assert entry.application_id == agent.agent_builder_id
    assert entry.workspace_id == agent.agent_builder.workspace_id

    restored = TrashHandler.restore_item(user, "agent_builder_agent", agent.id)
    assert restored.id == agent.id
    assert AgentDefinition.objects.get(id=agent.id).name == "Researcher"
    assert not TrashEntry.objects.filter(id=entry.id).exists()
    AgentService().delete_agent(user, agent.id)
    TrashEntry.objects.filter(
        trash_item_type="agent_builder_agent", trash_item_id=agent.id
    ).update(should_be_permanently_deleted=True)
    TrashHandler.permanently_delete_marked_trash()
    assert not AgentDefinition.objects_and_trash.filter(id=agent.id).exists()
    assert not TrashEntry.objects.filter(
        trash_item_type="agent_builder_agent", trash_item_id=agent.id
    ).exists()


@pytest.mark.django_db
def test_agent_builder_trash_hides_children_restores_and_cascades_cleanup(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    builder = enterprise_data_fixture.create_agent_builder_application(user=user)
    active = enterprise_data_fixture.create_agent_definition(agent_builder=builder)
    deleted = enterprise_data_fixture.create_agent_definition(agent_builder=builder)
    AgentService().delete_agent(user, deleted.id)
    CoreHandler().delete_application(user, builder)
    assert not AgentBuilder.objects.filter(id=builder.id).exists()
    assert not AgentDefinition.objects.filter(agent_builder_id=builder.id).exists()
    with pytest.raises(CannotRestoreChildBeforeParent):
        TrashHandler.restore_item(user, "agent_builder_agent", deleted.id)

    TrashHandler.restore_item(user, "application", builder.id)
    assert list(AgentDefinition.objects.filter(agent_builder_id=builder.id)) == [active]
    TrashHandler.restore_item(user, "agent_builder_agent", deleted.id)
    assert AgentDefinition.objects.filter(agent_builder_id=builder.id).count() == 2

    CoreHandler().delete_application(user, builder)
    TrashEntry.objects.filter(
        trash_item_type="application", trash_item_id=builder.id
    ).update(should_be_permanently_deleted=True)
    TrashHandler.permanently_delete_marked_trash()
    assert not Application.objects_and_trash.filter(id=builder.id).exists()
    assert not AgentDefinition.objects_and_trash.filter(
        agent_builder_id=builder.id
    ).exists()
    assert not TrashEntry.objects.filter(application_id=builder.id).exists()


@pytest.mark.django_db
def test_workspace_trash_hides_agent_definitions(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    agent = enterprise_data_fixture.create_agent_definition(user=user)
    workspace = agent.agent_builder.workspace
    TrashHandler.trash(user, workspace, None, workspace)
    assert not AgentDefinition.objects.filter(id=agent.id).exists()
    TrashHandler.restore_item(user, "workspace", workspace.id)
    assert AgentDefinition.objects.get(id=agent.id) == agent


@pytest.mark.django_db
def test_agent_builder_import_is_disabled_by_feature_flag(
    enterprise_data_fixture, settings
):
    workspace = enterprise_data_fixture.create_workspace()
    settings.FEATURE_FLAGS = []
    with pytest.raises(FeatureDisabledException):
        AgentBuilderApplicationType().import_serialized(
            workspace,
            {
                "id": 1,
                "name": "Team",
                "order": 1,
                "type": "agent_builder",
                "agents": [],
            },
            ImportExportConfig(include_permission_data=False),
            {},
        )
    assert not AgentBuilder.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("item_type", ["application", "agent_builder_agent"])
def test_restore_disabled_by_feature_flag(enterprise_data_fixture, settings, item_type):
    user = enterprise_data_fixture.create_user()
    agent = enterprise_data_fixture.create_agent_definition(user=user)
    builder = agent.agent_builder
    if item_type == "application":
        CoreHandler().delete_application(user, builder)
        item_id = builder.id
    else:
        AgentService().delete_agent(user, agent.id)
        item_id = agent.id
    settings.FEATURE_FLAGS = []
    with pytest.raises(FeatureDisabledException):
        TrashHandler.restore_item(user, item_type, item_id)
    assert TrashEntry.objects.filter(
        trash_item_type=item_type, trash_item_id=item_id
    ).exists()
    assert not AgentDefinition.objects.filter(id=agent.id).exists()


@pytest.mark.django_db
def test_permanent_cleanup_can_run_after_feature_flag_is_disabled(
    enterprise_data_fixture, settings
):
    user = enterprise_data_fixture.create_user()
    agent = enterprise_data_fixture.create_agent_definition(user=user)
    builder = agent.agent_builder
    AgentService().delete_agent(user, agent.id)
    CoreHandler().delete_application(user, builder)
    TrashEntry.objects.filter(
        trash_item_type="application", trash_item_id=builder.id
    ).update(should_be_permanently_deleted=True)
    settings.FEATURE_FLAGS = []
    TrashHandler.permanently_delete_marked_trash()
    assert not AgentBuilder.objects_and_trash.filter(id=builder.id).exists()
    assert not AgentDefinition.objects_and_trash.filter(id=agent.id).exists()
    assert not TrashEntry.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "operation", ["export", "export_action", "duplicate", "snapshot"]
)
def test_user_initiated_copies_exclude_agents_the_copier_cannot_read(
    enterprise_data_fixture,
    enable_enterprise,
    synced_roles,
    use_tmp_media_root,
    operation,
):
    owner = enterprise_data_fixture.create_user()
    member = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=owner, members=[member])
    builder = enterprise_data_fixture.create_agent_builder_application(
        workspace=workspace
    )
    visible = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, name="Visible"
    )
    hidden = enterprise_data_fixture.create_agent_definition(
        agent_builder=builder, name="Secret", order=2
    )
    roles = RoleAssignmentHandler()
    role = Role.objects.get(uid="BUILDER")
    if operation == "snapshot":
        snapshot_role = Role.objects.create(
            uid="agent_snapshot_builder", name="Snapshot builder", workspace=workspace
        )
        snapshot_role.operations.set(role.operations.all())
        snapshot_role.operations.add(
            *Operation.objects.filter(
                name__in=[
                    CreateSnapshotApplicationOperationType.type,
                    RestoreApplicationSnapshotOperationType.type,
                ]
            )
        )
        role = snapshot_role
        RoleAssignmentHandler._init = False
    roles.assign_role(member, workspace, role)
    roles.assign_role(
        member, workspace, Role.objects.get(uid="NO_ACCESS"), scope=hidden
    )
    if operation == "export":
        serialized = AgentBuilderApplicationType().export_serialized(
            builder, ImportExportConfig(include_permission_data=False, copied_by=member)
        )
        assert [agent["id"] for agent in serialized["agents"]] == [visible.id]
        assert "Secret" not in json.dumps(serialized)
    elif operation == "export_action":
        resource = ExportApplicationsActionType.do(member, workspace, [builder])
        archive_path = ImportExportHandler().get_export_storage_path(
            resource.get_archive_name()
        )
        with get_default_storage().open(archive_path, "rb") as archive_file:
            with ZipFile(archive_file) as archive:
                manifest = json.loads(archive.read("manifest.json"))
                app_manifest = manifest["applications"]["agent_builder"]["items"][0]
                serialized = json.loads(archive.read(app_manifest["files"]["schema"]))
        assert [agent["id"] for agent in serialized["agents"]] == [visible.id]
        assert "Secret" not in json.dumps(serialized)
    elif operation == "duplicate":
        copied = CoreHandler().duplicate_application(member, builder).specific
        assert list(copied.agents.values_list("name", flat=True)) == ["Visible"]
    else:
        snapshot = enterprise_data_fixture.create_snapshot(
            snapshot_from_application=builder,
            name="Restricted snapshot",
            created_by=member,
        )
        SnapshotHandler().perform_create(snapshot, Progress(total=100))
        snapshot.refresh_from_db()
        assert list(
            AgentDefinition.objects_and_trash.filter(
                agent_builder_id=snapshot.snapshot_to_application_id
            ).values_list("name", flat=True)
        ) == ["Visible"]
        restored = (
            SnapshotHandler().perform_restore(snapshot, Progress(total=100)).specific
        )
        assert list(restored.agents.values_list("name", flat=True)) == ["Visible"]
    assert AgentDefinition.objects.get(id=hidden.id).name == "Secret"
