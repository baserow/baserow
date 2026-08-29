import json
from unittest.mock import patch

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import DeltaToolCall, FunctionModel

from baserow.core.agents.service import AgentService
from baserow.core.handler import CoreHandler
from baserow.core.services.types import DispatchResult
from baserow_enterprise.agent_application.agent_dispatch_context import (
    AgentDispatchContext,
)
from baserow_enterprise.agent_application.data_providers import (
    agent_application_data_provider_type_registry,
)
from baserow_enterprise.agent_application.handler import (
    AgentApplicationHandler,
    AgentChatHandler,
)
from baserow_enterprise.agent_application.models import (
    AgentChat,
    AgentChatMessage,
    AgentTool,
)
from baserow_enterprise.agent_application.tasks import run_agent_chat
from baserow_enterprise.agent_application.tools.registries import (
    agent_tool_type_registry,
)
from baserow_enterprise.agent_application.tools.service_tool import (
    build_service_tool_schema,
    get_service_tool_name,
)

from .test_agent_runner import register_runner_test_model_type


def _tool_calling_model():
    def function(messages, info):
        if len(messages) == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="list_tables",
                        args='{"filters": {}, "thought": "Check the tables."}',
                        tool_call_id="call_1",
                    )
                ]
            )
        return ModelResponse(parts=[TextPart("Found the tables.")])

    async def stream_function(messages, info):
        if len(messages) == 1:
            yield {
                0: DeltaToolCall(
                    name="list_tables",
                    json_args='{"filters": {}, "thought": "Check the tables."}',
                    tool_call_id="call_1",
                )
            }
        else:
            yield "Found the tables."

    return FunctionModel(function, stream_function=stream_function)


@pytest.fixture
def workspace_tool_setup(data_fixture):
    register_runner_test_model_type()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace, name="CRM")
    table = data_fixture.create_database_table(
        user=user, database=database, name="Leads"
    )
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Agent")
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)
    AgentApplicationHandler().update_agent(
        agent,
        ai_generative_ai_type="agent_runner_test",
        ai_generative_ai_model="test-model",
    )
    identity = AgentService().create_agent(user, workspace, name="Agent identity")
    AgentApplicationHandler().set_agent_identity(application, identity)
    AgentTool.objects.create(agent=agent, type="workspace")
    return user, workspace, application, agent, table


@pytest.mark.django_db(transaction=True)
def test_workspace_tools_run_as_agent_identity(workspace_tool_setup):
    user, workspace, application, agent, table = workspace_tool_setup

    chat = AgentChat.objects.create(agent=agent, user=user)
    prompt = AgentChatHandler().create_message(
        chat, AgentChatMessage.Role.HUMAN, "Which tables exist?"
    )

    with (
        patch(
            "baserow_enterprise.agent_application.ai_models.resolve_agent_model",
            return_value=(_tool_calling_model(), {}),
        ),
        patch(
            "baserow_enterprise.agent_application.runner.resolve_agent_model",
            return_value=(_tool_calling_model(), {}),
        ),
        patch(
            "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
        ),
    ):
        run_agent_chat(chat.id, prompt.id)

    chat.refresh_from_db()
    assert chat.status == AgentChat.Status.IDLE, chat.error

    ai_message = chat.messages.filter(role=AgentChatMessage.Role.AI).get()
    assert ai_message.content == "Found the tables."

    events = ai_message.artifacts["events"]
    tool_calls = [e for e in events if e["type"] == "tool_call"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["tool_name"] == "list_tables"
    assert tool_calls[0]["result"]["status"] == "ok"
    # The tool executed as the agent identity and could see the table.
    assert "Leads" in json.dumps(tool_calls[0]["result"]["content"])


@pytest.mark.django_db
def test_workspace_tools_require_agent_identity(data_fixture):
    register_runner_test_model_type()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Agent")
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)
    AgentTool.objects.create(agent=agent, type="workspace")

    toolsets = agent_tool_type_registry.build_toolsets(agent, deps=None)

    assert toolsets == []


def test_service_tool_schema_and_name():
    tool = AgentTool(
        id=42,
        name="Send Slack update",
        config={
            "inputs": [
                {"name": "message", "type": "string", "description": "The text."},
                {"name": "urgent", "type": "boolean", "required": False},
            ]
        },
    )

    assert get_service_tool_name(tool) == "send_slack_update"
    schema = build_service_tool_schema(tool)
    assert schema["properties"]["message"] == {
        "type": "string",
        "description": "The text.",
    }
    assert schema["properties"]["urgent"] == {"type": "boolean"}
    assert schema["required"] == ["message"]

    unnamed = AgentTool(id=7, name="", config={})
    assert get_service_tool_name(unnamed) == "service_tool_7"


@pytest.mark.django_db
def test_agent_dispatch_context_data_providers(data_fixture):
    chat = AgentChat(event_payload={"results": [{"Name": "New lead"}]})
    dispatch_context = AgentDispatchContext(
        chat=chat, runtime_inputs={"message": "Hello"}
    )

    tool_input = agent_application_data_provider_type_registry.get("tool_input")
    assert tool_input.get_data_chunk(dispatch_context, ["message"]) == "Hello"

    trigger = agent_application_data_provider_type_registry.get("trigger")
    assert (
        trigger.get_data_chunk(dispatch_context, ["results", "0", "Name"]) == "New lead"
    )


@pytest.mark.django_db
def test_service_tool_dispatches_service(data_fixture, workspace_tool_setup):
    import asyncio

    from baserow_enterprise.agent_application.tools.service_tool import (
        build_service_tool,
    )

    user, workspace, application, agent, table = workspace_tool_setup
    service = data_fixture.create_core_http_request_service(url="'https://example.com'")
    tool = AgentTool.objects.create(
        agent=agent,
        type="service",
        name="Notify",
        config={"inputs": [{"name": "message", "type": "string"}]},
        service=service,
    )

    pydantic_tool = build_service_tool(tool, deps=None)
    assert pydantic_tool.name == "notify"

    captured = {}

    def fake_dispatch(service_arg, dispatch_context):
        captured["runtime_inputs"] = dispatch_context.runtime_inputs
        return DispatchResult(data={"status_code": 200})

    class FakeCtx:
        class deps:
            chat = None

            class tool_helpers:
                @staticmethod
                def raise_if_cancelled():
                    pass

    with patch(
        "baserow.core.services.handler.ServiceHandler.dispatch_service",
        side_effect=fake_dispatch,
    ):
        result = asyncio.run(pydantic_tool.function(FakeCtx(), message="Hello there"))

    assert result == {"status_code": 200}
    assert captured["runtime_inputs"] == {"message": "Hello there"}


def test_error_handling_toolset_translates_exceptions():
    import asyncio

    from baserow.core.exceptions import PermissionException, UserNotInWorkspace
    from baserow_enterprise.agent_application.tools.workspace import (
        ErrorHandlingToolset,
    )

    class FakeInner:
        def __init__(self, exc):
            self.exc = exc

        async def call_tool(self, name, tool_args, ctx, tool):
            raise self.exc

        async def get_tools(self, ctx):
            return {"switch_mode": object(), "list_tables": object()}

    denied = asyncio.run(
        ErrorHandlingToolset(FakeInner(PermissionException())).call_tool(
            "create_rows", {}, None, None
        )
    )
    assert "error" in denied

    outside = asyncio.run(
        ErrorHandlingToolset(FakeInner(UserNotInWorkspace())).call_tool(
            "list_rows", {}, None, None
        )
    )
    assert "error" in outside

    # Assistant-only tools are hidden from the agent.
    tools = asyncio.run(ErrorHandlingToolset(FakeInner(None)).get_tools(None))
    assert set(tools) == {"list_tables"}
