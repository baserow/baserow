from unittest.mock import patch

import pytest

from baserow.core.agents.service import AgentService
from baserow.core.exceptions import PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.utils import Progress
from baserow_enterprise.agent_application.handler import AgentApplicationHandler
from baserow_enterprise.agent_application.models import (
    AgentChat,
    AgentTool,
    AgentTrigger,
)
from baserow_enterprise.agent_application.triggers.handler import AgentTriggerHandler


@pytest.fixture
def configured_application(data_fixture):
    """
    A fully configured agent application: instructions/model, an identity,
    two triggers (rows created + periodic), a builtin and a service tool,
    and a chat that must never survive an export.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Agent")
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)
    AgentApplicationHandler().update_agent(
        agent,
        instructions="Watch the leads.",
        memory="Created table 42 last week.",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_temperature=0.7,
    )
    identity = AgentService().create_agent(user, workspace, name="Identity")
    AgentApplicationHandler().set_agent_identity(application, identity)

    integration = application.integrations.first().specific
    AgentTriggerHandler().create_trigger(
        user,
        application,
        "local_baserow_rows_created",
        service_values={"table_id": table.id, "integration_id": integration.id},
    )
    AgentTriggerHandler().create_trigger(
        user, application, "periodic", service_values={"interval": "DAY", "hour": 9}
    )

    AgentTool.objects.create(agent=agent, type="workspace")
    http_service = data_fixture.create_core_http_request_service(
        url="'https://example.com'"
    )
    AgentTool.objects.create(
        agent=agent,
        type="service",
        name="Notify",
        config={"inputs": [{"name": "message", "type": "string"}]},
        service=http_service,
        order=2,
    )

    AgentChat.objects.create(agent=agent, user=user, title="Do not export me")

    application.active = True
    application.save(update_fields=["active"])

    return user, workspace, database, table, application, agent, identity


def _assert_children_copied(new_application, table_id):
    new_agent = AgentApplicationHandler().get_main_agent(new_application)
    assert new_agent.instructions == "Watch the leads."
    assert new_agent.memory == "Created table 42 last week."
    assert new_agent.ai_generative_ai_model == "test_1"
    assert new_agent.ai_temperature == 0.7

    triggers = list(AgentTrigger.objects.filter(application=new_application))
    assert len(triggers) == 2
    service_types = {t.service.specific.get_type().type for t in triggers}
    assert service_types == {"local_baserow_rows_created", "periodic"}
    # The per-trigger enabled states survive the import; the imported
    # application itself must always start turned off.
    assert all(t.enabled is True for t in triggers)
    assert new_application.active is False
    rows_trigger = next(
        t
        for t in triggers
        if t.service.specific.get_type().type == "local_baserow_rows_created"
    )
    assert rows_trigger.service.specific.table_id == table_id

    tools = list(AgentTool.objects.filter(agent=new_agent).order_by("order"))
    assert [t.type for t in tools] == ["workspace", "service"]
    assert tools[1].name == "Notify"
    assert tools[1].config["inputs"][0]["name"] == "message"
    assert tools[1].service_id is not None

    assert not AgentChat.objects.filter(agent=new_agent).exists()
    return new_agent


@pytest.mark.django_db
def test_duplicate_agent_application(configured_application):
    user, workspace, database, table, application, agent, identity = (
        configured_application
    )

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        duplicated = CoreHandler().duplicate_application(user, application).specific

    assert duplicated.id != application.id
    assert duplicated.workspace_id == workspace.id
    _assert_children_copied(duplicated, table.id)

    # A same-workspace duplicate keeps the identity, and the integrations act
    # as it again.
    assert duplicated.agent_identity_id == identity.id
    duplicated_integration = duplicated.integrations.first().specific
    assert duplicated_integration.authorized_agent_id == identity.id

    # The original is untouched: still active with enabled triggers.
    application.refresh_from_db()
    assert application.active is True
    assert (
        AgentTrigger.objects.filter(application=application, enabled=True).count() == 2
    )


@pytest.mark.django_db
def test_snapshot_and_restore_agent_application(configured_application):
    user, workspace, database, table, application, agent, identity = (
        configured_application
    )

    snapshot = SnapshotHandler().create(application.id, user, "agent snapshot")
    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        SnapshotHandler().perform_create(snapshot, Progress(total=100))

        snapshot.refresh_from_db()
        snapshotted = snapshot.snapshot_to_application.specific
        # The snapshot copy must not carry the identity and must be off.
        assert snapshotted.agent_identity_id is None
        assert snapshotted.active is False

        restored = (
            SnapshotHandler().perform_restore(snapshot, Progress(total=100)).specific
        )

    assert restored.workspace_id == workspace.id
    _assert_children_copied(restored, table.id)
    assert restored.agent_identity_id is None


@pytest.mark.django_db
def test_template_style_import_remaps_tables(configured_application, data_fixture):
    user, workspace, database, table, application, agent, identity = (
        configured_application
    )
    other_workspace = data_fixture.create_workspace(user=user)

    config = ImportExportConfig(
        include_permission_data=False, reduce_disk_space_usage=True
    )
    database_type = application_type_registry.get("database")
    agent_type = application_type_registry.get("agent")

    serialized_database = database_type.export_serialized(database.specific, config)
    serialized_agent_app = agent_type.export_serialized(application, config)

    id_mapping = {}
    imported_database = database_type.import_serialized(
        other_workspace, serialized_database, config, id_mapping
    )
    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        imported_application = agent_type.import_serialized(
            other_workspace, serialized_agent_app, config, id_mapping
        ).specific

    new_table = imported_database.specific.table_set.get()
    assert new_table.id != table.id
    _assert_children_copied(imported_application, new_table.id)
    # Identities never cross workspaces.
    assert imported_application.agent_identity_id is None


@pytest.mark.django_db
def test_template_workspace_allows_read_only_access(
    configured_application, data_fixture
):
    user, workspace, database, table, application, agent, identity = (
        configured_application
    )
    data_fixture.create_template(workspace=workspace)
    outsider = data_fixture.create_user()

    for operation in [
        "agent_application.read_agent",
        "agent_application.read_trigger",
        "agent_application.list_tools",
        "agent_application.list_chats",
        "agent_application.read_chat",
        "agent_application.read_usage",
    ]:
        assert CoreHandler().check_permissions(
            outsider,
            operation,
            workspace=workspace,
            context=application.application_ptr,
        ), f"{operation} should be allowed on a template workspace"

    for operation in [
        "agent_application.update_agent",
        "agent_application.update_trigger",
        "agent_application.create_tool",
        "agent_application.run_chat",
    ]:
        with pytest.raises(PermissionException):
            CoreHandler().check_permissions(
                outsider,
                operation,
                workspace=workspace,
                context=application.application_ptr,
            )
