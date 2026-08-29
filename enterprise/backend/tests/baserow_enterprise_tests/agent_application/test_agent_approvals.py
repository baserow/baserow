from unittest.mock import patch

import pytest
from pydantic_ai.messages import (
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.toolsets import FunctionToolset

from baserow.api.generative_ai.serializers import GenerativeAIModelsSerializer
from baserow.core.generative_ai.registries import (
    GenerativeAIModelType,
    generative_ai_model_type_registry,
)
from baserow.core.handler import CoreHandler
from baserow_enterprise.agent_application.exceptions import (
    AgentChatAwaitingApproval,
    AgentToolApprovalDoesNotExist,
)
from baserow_enterprise.agent_application.handler import (
    AgentApplicationHandler,
    AgentChatHandler,
)
from baserow_enterprise.agent_application.models import (
    AgentChat,
    AgentChatMessage,
    AgentChatToolApproval,
    AgentTool,
)
from baserow_enterprise.agent_application.tasks import run_agent_chat
from baserow_enterprise.agent_application.tools.gating import wrap_approval_required
from baserow_enterprise.agent_application.tools.registries import (
    AgentToolType,
    agent_tool_type_registry,
)

FINAL_ANSWER = "All done."
EXECUTED = []


def _wants_tool_call(messages) -> bool:
    last_parts = messages[-1].parts
    return not any(isinstance(part, ToolReturnPart) for part in last_parts)


def _model_function(messages, info):
    if _wants_tool_call(messages):
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="approval_test_write",
                    args={"value": 1},
                    tool_call_id="call_1",
                )
            ]
        )
    return ModelResponse(parts=[TextPart(FINAL_ANSWER)])


async def _stream_function(messages, info):
    from pydantic_ai.models.function import DeltaToolCall

    if _wants_tool_call(messages):
        yield {
            0: DeltaToolCall(
                name="approval_test_write",
                json_args='{"value": 1}',
                tool_call_id="call_1",
            )
        }
    else:
        yield FINAL_ANSWER


class AgentApprovalTestModelType(GenerativeAIModelType):
    type = "agent_approval_test"

    def is_enabled(self, workspace=None):
        return True

    def get_enabled_models(self, workspace=None, settings_override=None):
        return ["test-model"]

    def get_ai_model(self, model_name, workspace=None, settings_override=None):
        return FunctionModel(_model_function, stream_function=_stream_function)

    def prompt(self, *args, **kwargs):
        return FINAL_ANSWER

    def get_settings_serializer(self):
        return GenerativeAIModelsSerializer


class ApprovalTestToolType(AgentToolType):
    type = "approval_test"

    def build_toolsets(self, tool, deps):
        def approval_test_write(value: int) -> str:
            """Writes something."""

            EXECUTED.append(value)
            return "written"

        toolset = FunctionToolset([approval_test_write])
        if tool.config.get("require_approval", True):
            return [wrap_approval_required(toolset)]
        return [toolset]


def _register_test_types():
    for registry, instance in [
        (generative_ai_model_type_registry, AgentApprovalTestModelType()),
        (agent_tool_type_registry, ApprovalTestToolType()),
    ]:
        try:
            registry.register(instance)
        except registry.already_registered_exception_class:
            pass


@pytest.fixture
def approval_setup(data_fixture):
    _register_test_types()
    EXECUTED.clear()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Agent")
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)
    AgentApplicationHandler().update_agent(
        agent,
        ai_generative_ai_type="agent_approval_test",
        ai_generative_ai_model="test-model",
    )
    AgentTool.objects.create(agent=agent, type="approval_test")
    return user, workspace, application, agent


def _start_run(agent, user, content="Please write."):
    chat = AgentChat.objects.create(agent=agent, user=user)
    prompt = AgentChatHandler().create_message(
        chat, AgentChatMessage.Role.HUMAN, content
    )
    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        run_agent_chat(chat.id, prompt.id)
    chat.refresh_from_db()
    return chat


@pytest.mark.django_db(transaction=True)
def test_write_tool_call_pauses_run_for_approval(approval_setup):
    user, workspace, application, agent = approval_setup

    chat = _start_run(agent, user)

    assert chat.status == AgentChat.Status.AWAITING_APPROVAL
    assert EXECUTED == []

    approvals = list(chat.tool_approvals.all())
    assert len(approvals) == 1
    approval = approvals[0]
    assert approval.status == AgentChatToolApproval.Status.PENDING
    assert approval.tool_name == "approval_test_write"
    assert approval.tool_args == {"value": 1}
    assert approval.tool_call_id == "call_1"

    ai_message = chat.messages.filter(role=AgentChatMessage.Role.AI).get()
    assert ai_message.artifacts["approvals"][0]["tool_name"] == "approval_test_write"
    # The pending tool call is preserved in the history for the resume.
    assert chat.message_history


@pytest.mark.django_db(transaction=True)
def test_approving_resumes_run_and_executes_tool(approval_setup):
    user, workspace, application, agent = approval_setup

    chat = _start_run(agent, user)
    approval = chat.tool_approvals.get()

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        AgentChatHandler().decide_tool_approvals(
            chat, user, [{"id": approval.id, "approved": True}]
        )

    chat.refresh_from_db()
    approval.refresh_from_db()
    assert chat.status == AgentChat.Status.IDLE
    assert approval.status == AgentChatToolApproval.Status.APPROVED
    assert approval.decided_by_id == user.id
    assert approval.decided_at is not None
    assert EXECUTED == [1]

    final_message = chat.messages.filter(role=AgentChatMessage.Role.AI).last()
    assert final_message.content == FINAL_ANSWER


@pytest.mark.django_db(transaction=True)
def test_rejecting_feeds_reason_back_without_executing(approval_setup):
    user, workspace, application, agent = approval_setup

    chat = _start_run(agent, user)
    approval = chat.tool_approvals.get()

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        AgentChatHandler().decide_tool_approvals(
            chat,
            user,
            [{"id": approval.id, "approved": False, "reason": "Wrong table."}],
        )

    chat.refresh_from_db()
    approval.refresh_from_db()
    assert chat.status == AgentChat.Status.IDLE
    assert approval.status == AgentChatToolApproval.Status.REJECTED
    assert EXECUTED == []
    # The model received the rejection reason as the tool result.
    assert b"Wrong table." in bytes(chat.message_history)

    final_message = chat.messages.filter(role=AgentChatMessage.Role.AI).last()
    assert final_message.content == FINAL_ANSWER


@pytest.mark.django_db(transaction=True)
def test_cannot_send_message_while_awaiting_approval(approval_setup):
    user, workspace, application, agent = approval_setup

    chat = _start_run(agent, user)
    message = AgentChatMessage.objects.create(
        chat=chat, role=AgentChatMessage.Role.HUMAN, content="More work."
    )

    with pytest.raises(AgentChatAwaitingApproval):
        AgentChatHandler().start_chat_run(chat, message)


@pytest.mark.django_db(transaction=True)
def test_cancel_rejects_all_pending_approvals(approval_setup):
    user, workspace, application, agent = approval_setup

    chat = _start_run(agent, user)

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        AgentChatHandler().cancel_chat_run(chat, user)

    chat.refresh_from_db()
    assert chat.status == AgentChat.Status.IDLE
    assert EXECUTED == []
    assert chat.tool_approvals.get().status == AgentChatToolApproval.Status.REJECTED


@pytest.mark.django_db(transaction=True)
def test_deciding_unknown_approval_raises(approval_setup):
    user, workspace, application, agent = approval_setup

    chat = _start_run(agent, user)

    with pytest.raises(AgentToolApprovalDoesNotExist):
        AgentChatHandler().decide_tool_approvals(
            chat, user, [{"id": 999999, "approved": True}]
        )


@pytest.mark.django_db(transaction=True)
def test_tool_without_approval_requirement_runs_directly(approval_setup):
    user, workspace, application, agent = approval_setup

    agent.tools.filter(type="approval_test").update(config={"require_approval": False})

    chat = _start_run(agent, user)

    assert chat.status == AgentChat.Status.IDLE
    assert EXECUTED == [1]
    assert chat.tool_approvals.count() == 0


@pytest.mark.django_db(transaction=True)
def test_pending_approvals_overview_and_count(approval_setup, api_client, data_fixture):
    user, workspace, application, agent = approval_setup
    token = data_fixture.generate_token(user)

    chat = _start_run(agent, user)
    approval = chat.tool_approvals.get()

    response = api_client.get(
        f"/api/agent_application/{application.id}/approvals/",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200
    listed = response.json()
    assert len(listed) == 1
    assert listed[0]["id"] == approval.id
    assert listed[0]["tool_name"] == "approval_test_write"
    assert listed[0]["chat_uuid"] == str(chat.uuid)
    assert "chat_title" in listed[0]

    # The application serializer exposes the pending count for the sidebar
    # and header indicators.
    response = api_client.get(
        f"/api/applications/workspace/{workspace.id}/",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200
    agent_app = next(a for a in response.json() if a["id"] == application.id)
    assert agent_app["pending_approvals_count"] == 1

    # Deciding empties the overview and the count.
    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
    ):
        AgentChatHandler().decide_tool_approvals(
            chat, user, [{"id": approval.id, "approved": False}]
        )

    response = api_client.get(
        f"/api/agent_application/{application.id}/approvals/",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.json() == []


@pytest.mark.django_db(transaction=True)
def test_pending_approvals_broadcast_to_workspace(approval_setup):
    user, workspace, application, agent = approval_setup

    with patch(
        "baserow_enterprise.agent_application.realtime.broadcast_to_permitted_users"
    ) as broadcast_mock:
        chat = _start_run(agent, user)

    payload = broadcast_mock.delay.call_args[0][4]
    assert payload["type"] == "agent_pending_approvals_updated"
    assert payload["application_id"] == application.id
    assert payload["count"] == 1

    approval = chat.tool_approvals.get()
    with (
        patch(
            "baserow_enterprise.agent_application.realtime.broadcast_to_channel_group"
        ),
        patch(
            "baserow_enterprise.agent_application.realtime.broadcast_to_permitted_users"
        ) as decide_broadcast_mock,
    ):
        AgentChatHandler().decide_tool_approvals(
            chat, user, [{"id": approval.id, "approved": False}]
        )

    payload = decide_broadcast_mock.delay.call_args[0][4]
    assert payload["type"] == "agent_pending_approvals_updated"
    assert payload["count"] == 0
