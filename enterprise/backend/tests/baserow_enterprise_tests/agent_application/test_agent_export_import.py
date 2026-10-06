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


# ---------------------------------------------------------------------------
# Platform compatibility: what leaves the workspace and what a copy keeps
# ---------------------------------------------------------------------------


def _export_config(**overrides):
    values = {"include_permission_data": False}
    values.update(overrides)
    return ImportExportConfig(**values)


@pytest.mark.django_db
def test_export_strips_workspace_ids_and_secrets_unless_duplicating(
    configured_application,
):
    user, workspace, database, table, application, agent, identity = (
        configured_application
    )
    workspace_tool = AgentTool.objects.get(agent=agent, type="workspace")
    workspace_tool.config = {"access": "everything", "tool_identities": {"x": 1}}
    workspace_tool.save()
    AgentTool.objects.create(
        agent=agent,
        type="mcp",
        name="MCP",
        config={"url": "https://mcp.example.com", "headers": {"Authorization": "s"}},
        order=3,
    )
    application_type = application_type_registry.get("agent")

    exported = application_type.export_serialized(application, _export_config())
    tools = {tool["type"]: tool for tool in exported["tools"]}
    assert "tool_identities" not in tools["workspace"]["config"]
    assert tools["mcp"]["config"]["headers"] == {}
    assert tools["mcp"]["config"]["url"] == "https://mcp.example.com"
    assert all(tool["identity_id"] is None for tool in exported["tools"])
    # Integration secrets honour the export config like other applications.
    assert exported["integrations"][0]["authorized_user"] is None

    duplicated = application_type.export_serialized(
        application, _export_config(is_duplicate=True)
    )
    tools = {tool["type"]: tool for tool in duplicated["tools"]}
    assert tools["workspace"]["config"]["tool_identities"] == {"x": 1}
    assert tools["mcp"]["config"]["headers"] == {"Authorization": "s"}


@pytest.mark.django_db
def test_duplicate_keeps_tool_identity_and_renews_public_links(
    configured_application, data_fixture
):
    from baserow_enterprise.agent_application.channels.web import (
        WebAgentChatChannelType,
    )
    from baserow_enterprise.agent_application.models import AgentChatChannel

    user, workspace, database, table, application, agent, identity = (
        configured_application
    )
    service_tool = AgentTool.objects.get(agent=agent, type="service")
    service_tool.identity = identity
    service_tool.save()
    web_type = WebAgentChatChannelType()
    channel = AgentChatChannel.objects.create(
        application=application,
        type="web",
        name="Web",
        config=web_type.prepare_config({"title": "Help"}),
    )

    duplicate = CoreHandler().duplicate_application(user, application).specific

    new_agent = AgentApplicationHandler().get_main_agent(duplicate)
    assert AgentTool.objects.get(agent=new_agent, type="service").identity == identity
    copy = AgentChatChannel.objects.get(application=duplicate, type="web")
    assert copy.config["title"] == "Help"
    assert copy.config["slug"] != channel.config["slug"]
    assert copy.uid != channel.uid
    # The original keeps answering to its own link.
    from baserow_enterprise.agent_application.handler import AgentChatHandler

    assert AgentChatHandler().get_public_web_channel(channel.config["slug"]) == channel
    # The copy starts inactive like every import; once turned on, its own
    # link resolves to it and not to the original.
    duplicate.active = True
    duplicate.save(update_fields=["active"])
    assert AgentChatHandler().get_public_web_channel(copy.config["slug"]) == copy


@pytest.mark.django_db
def test_pinned_conversations_travel_as_examples_but_not_on_duplicate(
    configured_application,
):
    from baserow_enterprise.agent_application.models import AgentChatMessage

    user, workspace, database, table, application, agent, identity = (
        configured_application
    )
    example = AgentChat.objects.create(
        agent=agent, user=user, title="How it works", pinned=True, source="manual"
    )
    AgentChatMessage.objects.create(chat=example, role="human", content="Hi there")
    AgentChatMessage.objects.create(
        chat=example,
        role="ai",
        content="Hello! I watch the leads.",
        artifacts={"events": [{"type": "tool_call", "name": "list_rows"}]},
    )
    AgentChatMessage.objects.create(chat=example, role="system", content="internal")
    application_type = application_type_registry.get("agent")

    exported = application_type.export_serialized(application, _export_config())
    assert exported["agents"][0]["example_chats"] == [
        {
            "title": "How it works",
            "messages": [
                {"role": "human", "content": "Hi there", "artifacts": {}},
                {
                    "role": "ai",
                    "content": "Hello! I watch the leads.",
                    "artifacts": {
                        "events": [{"type": "tool_call", "name": "list_rows"}]
                    },
                },
            ],
        }
    ]
    assert "message_history" not in str(exported["agents"][0]["example_chats"])

    imported = application_type.import_serialized(
        workspace, exported, _export_config(), {}
    ).specific
    chats = list(AgentChat.objects.filter(agent__application=imported))
    assert len(chats) == 1
    assert chats[0].title == "How it works"
    assert chats[0].pinned is True
    assert chats[0].user_id is None
    assert chats[0].status == AgentChat.Status.IDLE
    assert chats[0].message_history is None
    assert list(chats[0].messages.values_list("role", flat=True)) == ["human", "ai"]

    duplicated = application_type.export_serialized(
        application, _export_config(is_duplicate=True)
    )
    assert duplicated["agents"][0]["example_chats"] == []


@pytest.mark.django_db
def test_import_survives_a_trashed_integration(configured_application):
    user, workspace, database, table, application, agent, identity = (
        configured_application
    )
    integration = application.integrations.first()
    service_tool = AgentTool.objects.get(agent=agent, type="service")
    service_tool.service.integration = integration
    service_tool.service.save()
    integration.trashed = True
    integration.save()

    duplicate = CoreHandler().duplicate_application(user, application).specific

    new_agent = AgentApplicationHandler().get_main_agent(duplicate)
    copied_tool = AgentTool.objects.get(agent=new_agent, type="service")
    assert copied_tool.service is not None
    assert copied_tool.service.integration_id is None


@pytest.mark.django_db
def test_template_install_falls_back_to_the_workspace_model(configured_application):
    from unittest.mock import patch

    user, workspace, database, table, application, agent, identity = (
        configured_application
    )
    application_type = application_type_registry.get("agent")
    exported = application_type.export_serialized(application, _export_config())
    install_config = ImportExportConfig(
        include_permission_data=False, is_duplicate=True, is_template=True
    )

    with patch(
        "baserow_enterprise.agent_application.handler.AgentApplicationHandler"
        ".pick_default_model",
        return_value=("openai", "gpt-default"),
    ):
        installed = application_type.import_serialized(
            workspace, exported, install_config, {}
        ).specific

    installed_agent = AgentApplicationHandler().get_main_agent(installed)
    assert installed_agent.ai_generative_ai_type == "openai"
    assert installed_agent.ai_generative_ai_model == "gpt-default"
    # A template install is a duplicate of the template's workspace, so
    # nothing workspace specific of this workspace is linked.
    assert installed.agent_identity_id is None
    assert installed_agent.agent_skills.count() == 0

    # A plain duplicate keeps the author's model.
    duplicate = CoreHandler().duplicate_application(user, application).specific
    assert (
        AgentApplicationHandler().get_main_agent(duplicate).ai_generative_ai_model
        == "test_1"
    )


@pytest.mark.django_db
def test_template_install_drops_table_ids_of_another_installation(
    configured_application,
):
    user, workspace, database, table, application, agent, identity = (
        configured_application
    )
    application_type = application_type_registry.get("agent")
    exported = application_type.export_serialized(application, _export_config())
    install_config = ImportExportConfig(
        include_permission_data=False, is_duplicate=True, is_template=True
    )

    # The database of the template is in the mapping, but this table is not:
    # it belongs to another installation and must not be kept.
    installed = application_type.import_serialized(
        workspace, exported, install_config, {"database_tables": {}}
    ).specific

    trigger = next(
        t
        for t in AgentTrigger.objects.filter(application=installed)
        if t.service.specific.get_type().type == "local_baserow_rows_created"
    )
    assert trigger.service.specific.table_id is None
