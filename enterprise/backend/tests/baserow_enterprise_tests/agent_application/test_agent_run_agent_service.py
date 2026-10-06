"""
The "Run agent" service: one service type that starts an agent conversation
from a button, an automation, an application builder action or, as a tool,
from another agent.
"""

from unittest.mock import patch

import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
    UnexpectedDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import service_type_registry
from baserow_enterprise.agent_application.agent_dispatch_context import (
    AgentDispatchContext,
)
from baserow_enterprise.agent_application.handler import AgentApplicationHandler
from baserow_enterprise.agent_application.models import AgentChat, AgentChatMessage
from baserow_enterprise.agent_application.tools.handler import AgentToolHandler
from baserow_enterprise.integrations.core.service_types import (
    CoreRunAgentServiceType,
)

from .test_agent_runner import TEST_ANSWER, register_runner_test_model_type

BROADCAST = "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"


class PlainDispatchContext(DispatchContext):
    """A host that only knows its workspace, like an automation does."""

    def range(self, service):
        return [0, None]


def _create_agent(user, workspace, name="Target"):
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name=name)
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)
    AgentApplicationHandler().update_agent(
        agent,
        ai_generative_ai_type="agent_runner_test",
        ai_generative_ai_model="test-model",
    )
    return application, agent


@pytest.fixture
def setup(enterprise_data_fixture):
    register_runner_test_model_type()
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    application, agent = _create_agent(user, workspace)
    service = enterprise_data_fixture.create_enterprise_core_run_agent_service(
        agent_application=application, prompt="'Summarise ticket 12'"
    )
    return user, workspace, application, agent, service


@pytest.mark.django_db
def test_dispatch_queues_a_conversation_and_returns_its_link(setup):
    user, workspace, application, agent, service = setup

    with (
        patch(BROADCAST),
        patch("baserow_enterprise.agent_application.tasks.run_agent_chat.delay") as run,
    ):
        result = ServiceHandler().dispatch_service(
            service, PlainDispatchContext(workspace=workspace, actor=user)
        )

    chat = AgentChat.objects.get(agent=agent)
    assert chat.source == AgentChat.Source.SERVICE
    assert chat.user_id == user.id
    assert chat.parent_chat_id is None
    assert chat.status == AgentChat.Status.IN_PROGRESS
    assert chat.title == "Summarise ticket 12"
    message = chat.messages.get()
    assert message.role == AgentChatMessage.Role.HUMAN
    assert message.content == "Summarise ticket 12"
    assert result.data == {
        "chat_uuid": str(chat.uuid),
        "url": f"http://localhost:3000/agent/{application.id}?chat={chat.uuid}",
        "status": "in_progress",
        "answer": None,
    }
    assert run.call_count == 0  # on_commit, never runs inside the test transaction


@pytest.mark.django_db(transaction=True)
def test_dispatch_can_wait_for_the_answer(setup):
    user, workspace, application, agent, service = setup
    service.wait_for_result = True
    service.save()

    with patch(BROADCAST):
        result = ServiceHandler().dispatch_service(
            service, PlainDispatchContext(workspace=workspace)
        )

    chat = AgentChat.objects.get(agent=agent)
    assert chat.user_id is None  # automations run as the system
    assert chat.status == AgentChat.Status.IDLE, chat.error
    assert result.data["answer"] == TEST_ANSWER
    assert result.data["status"] == AgentChat.Status.IDLE


@pytest.mark.django_db(transaction=True)
def test_an_agent_can_run_another_agent_as_a_tool(enterprise_data_fixture, setup):
    user, workspace, target_application, target_agent, service = setup
    parent_application, parent_agent = _create_agent(user, workspace, "Parent")
    parent_chat = AgentChat.objects.create(agent=parent_agent, user=user)

    with patch(BROADCAST):
        result = ServiceHandler().dispatch_service(
            service, AgentDispatchContext(chat=parent_chat, actor=user)
        )

    child = AgentChat.objects.get(agent=target_agent)
    # A tool call always waits for the answer, whatever the switch says.
    assert child.parent_chat_id == parent_chat.id
    assert child.status == AgentChat.Status.IDLE, child.error
    assert result.data["answer"] == TEST_ANSWER

    # An agent cannot call itself, and chains stop at the depth limit.
    own_service = enterprise_data_fixture.create_enterprise_core_run_agent_service(
        agent_application=parent_application, prompt="'again'"
    )
    with pytest.raises(UnexpectedDispatchException):
        ServiceHandler().dispatch_service(
            own_service, AgentDispatchContext(chat=parent_chat, actor=user)
        )
    grandchild_application, grandchild_agent = _create_agent(user, workspace, "Leaf")
    leaf_service = enterprise_data_fixture.create_enterprise_core_run_agent_service(
        agent_application=grandchild_application, prompt="'deeper'"
    )
    with pytest.raises(UnexpectedDispatchException):
        ServiceHandler().dispatch_service(
            leaf_service, AgentDispatchContext(chat=child, actor=user)
        )


@pytest.mark.django_db
def test_dispatch_checks_the_actor_and_the_workspace(enterprise_data_fixture, setup):
    user, workspace, application, agent, service = setup
    stranger = enterprise_data_fixture.create_user()
    other_workspace = enterprise_data_fixture.create_workspace(user=user)

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        ServiceHandler().dispatch_service(
            service, PlainDispatchContext(workspace=workspace, actor=stranger)
        )
    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        ServiceHandler().dispatch_service(
            service, PlainDispatchContext(workspace=other_workspace, actor=user)
        )
    assert not AgentChat.objects.filter(agent=agent).exists()

    service.prompt = "''"
    service.save()
    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        ServiceHandler().dispatch_service(
            service, PlainDispatchContext(workspace=workspace, actor=user)
        )


@pytest.mark.django_db
def test_configuring_the_agent_is_scoped_to_the_workspace(
    enterprise_data_fixture, setup
):
    user, workspace, application, agent, service = setup
    other_workspace = enterprise_data_fixture.create_workspace(user=user)
    other_application, other_agent = _create_agent(user, other_workspace, "Other")
    stranger = enterprise_data_fixture.create_user()
    service_type = CoreRunAgentServiceType()

    assert (
        service_type.get_agent_application_to_run(user, application.id, workspace.id)
        == application
    )
    with pytest.raises(DRFValidationError):
        service_type.get_agent_application_to_run(
            user, other_application.id, workspace.id
        )
    with pytest.raises(DRFValidationError):
        service_type.get_agent_application_to_run(stranger, application.id)

    # As an action tool the target must sit in the calling agent's workspace.
    caller_application, caller_agent = _create_agent(user, workspace, "Caller")
    with pytest.raises(DRFValidationError):
        AgentToolHandler().create_tool(
            user,
            caller_agent,
            "service",
            service_type_str="run_agent",
            service_values={"agent_application_id": other_application.id},
        )
    tool = AgentToolHandler().create_tool(
        user,
        caller_agent,
        "service",
        service_type_str="run_agent",
        service_values={"agent_application_id": application.id, "prompt": "'hi'"},
    )
    assert tool.service.specific.agent_application_id == application.id


@pytest.mark.django_db
def test_export_import_remaps_or_drops_the_agent(enterprise_data_fixture, setup):
    user, workspace, application, agent, service = setup
    service_type = service_type_registry.get("run_agent")
    serialized = service_type.export_serialized(service)
    assert serialized["agent_application_id"] == application.id

    def reimport(id_mapping, config):
        return ServiceHandler().import_service(
            None, dict(serialized), id_mapping, import_export_config=config
        )

    remapped, _ = _create_agent(user, workspace, "Copy")
    imported = reimport(
        {
            "applications": {application.id: remapped.id},
            "import_workspace_id": workspace.id,
        },
        ImportExportConfig(
            include_permission_data=False, reduce_disk_space_usage=False
        ),
    )
    assert imported.agent_application_id == remapped.id

    duplicate = reimport(
        {"import_workspace_id": workspace.id},
        ImportExportConfig(
            include_permission_data=False,
            reduce_disk_space_usage=False,
            is_duplicate=True,
        ),
    )
    assert duplicate.agent_application_id == application.id

    # A template or a file import never keeps a reference it did not remap.
    template = reimport(
        {"import_workspace_id": workspace.id},
        ImportExportConfig(
            include_permission_data=False,
            reduce_disk_space_usage=False,
            is_duplicate=True,
            is_template=True,
        ),
    )
    assert template.agent_application_id is None
    file_import = reimport(
        {},
        ImportExportConfig(
            include_permission_data=False, reduce_disk_space_usage=False
        ),
    )
    assert file_import.agent_application_id is None


def test_the_service_is_offered_by_every_host():
    assert service_type_registry.get("run_agent").type == "run_agent"
    assert automation_node_type_registry.get("run_agent").service_type == "run_agent"
    assert (
        builder_workflow_action_type_registry.get("run_agent").service_type
        == "run_agent"
    )
    assert (
        database_workflow_action_type_registry.get("run_agent").service_type
        == "run_agent"
    )
    schema = service_type_registry.get("run_agent").generate_schema(
        type("S", (), {"id": 1, "agent_application": None})()
    )
    assert set(schema["properties"]) == {"chat_uuid", "url", "status", "answer"}
    assert schema["title"] == "Run agent"


@pytest.mark.django_db
def test_the_result_is_named_after_the_agent(setup):
    user, workspace, application, agent, service = setup
    schema = service_type_registry.get("run_agent").generate_schema(service)
    assert schema["title"] == application.name


@pytest.mark.django_db
def test_every_host_configures_the_agent_within_its_workspace(
    enterprise_data_fixture, setup
):
    from baserow.contrib.automation.nodes.service import AutomationNodeService
    from baserow.contrib.builder.workflow_actions.service import (
        BuilderWorkflowActionService,
    )
    from baserow.contrib.database.workflow_actions.service import (
        DatabaseWorkflowActionService,
    )

    user, workspace, application, agent, service = setup
    other_workspace = enterprise_data_fixture.create_workspace(user=user)
    other_application, _ = _create_agent(user, other_workspace, "Other")

    # Fresh dicts per call: a host must not depend on the caller's copy.
    def values():
        return {"agent_application_id": application.id, "prompt": "'hi'"}

    def foreign():
        return {"agent_application_id": other_application.id, "prompt": "'hi'"}

    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(user=user, database=database)
    button = enterprise_data_fixture.create_button_field(table=table, label="Go")
    button_type = database_workflow_action_type_registry.get("run_agent")
    action = DatabaseWorkflowActionService().create_workflow_action(
        user, button_type, button, service=values()
    )
    assert action.service.specific.agent_application_id == application.id
    with pytest.raises(DRFValidationError):
        DatabaseWorkflowActionService().create_workflow_action(
            user, button_type, button, service=foreign()
        )

    builder = enterprise_data_fixture.create_builder_application(workspace=workspace)
    page = enterprise_data_fixture.create_builder_page(builder=builder)
    builder_type = builder_workflow_action_type_registry.get("run_agent")
    builder_action = BuilderWorkflowActionService().create_workflow_action(
        user, builder_type, page, service={**values(), "wait_for_result": True}
    )
    builder_service = builder_action.service.specific
    assert builder_service.agent_application_id == application.id
    # A published application never waits on a model.
    assert builder_service.wait_for_result is False
    with pytest.raises(DRFValidationError):
        BuilderWorkflowActionService().create_workflow_action(
            user, builder_type, page, service=foreign()
        )

    automation = enterprise_data_fixture.create_automation_application(
        workspace=workspace
    )
    workflow = enterprise_data_fixture.create_automation_workflow(
        user=user, automation=automation
    )
    node_type = automation_node_type_registry.get("run_agent")
    placement = {
        "reference_node_id": workflow.get_trigger().id,
        "position": "south",
        "output": "",
    }
    node = AutomationNodeService
