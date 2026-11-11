from unittest.mock import Mock
from uuid import uuid4

from django.contrib.auth.models import AbstractUser

import pytest
from pydantic_ai import WebSearchTool
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import (
    NativeToolCallPart,
    NativeToolReturnPart,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)
from pydantic_ai.models.function import DeltaToolCall, FunctionModel
from pydantic_ai.profiles import ModelProfile

from baserow.contrib.agent.actions import (
    CreateAgentConversationActionType,
    UpdateAgentConfigurationActionType,
)
from baserow.contrib.agent.application_types import AgentApplicationType
from baserow.contrib.agent.constants import (
    WEB_SEARCH_FAILED_INSTRUCTIONS,
    WEB_SEARCH_INSTRUCTIONS,
    WEB_SEARCH_UNAVAILABLE_INSTRUCTIONS,
)
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentApplication, AgentMessage
from baserow.contrib.agent.replies import AgentResponder, _web_search_step_input
from baserow.contrib.agent.service import AgentService
from baserow.contrib.database.table.models import Table
from baserow.contrib.integrations.mcp.models import MCPServerTool
from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel
from baserow.core.chat_runs.models import ChatRun
from baserow.core.generative_ai.constants import WEB_SEARCH_MAX_PER_REPLY
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.models import Agent as Identity
from baserow.core.registries import ImportExportConfig

from .utils import agent_url, run_reply

CALL = NativeToolCallPart(
    tool_name=WebSearchTool.kind, args={"query": "baserow"}, tool_call_id="search-1"
)
RESULT = NativeToolReturnPart(
    tool_name=WebSearchTool.kind, content=[], tool_call_id="search-1"
)


def use_stream(mocker, stream) -> None:
    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(FunctionModel(stream_function=stream), {}),
    )


def answer(user, agent) -> AgentMessage:
    created = CreateAgentConversationActionType.do(
        user, agent.id, uuid4(), uuid4(), "Hi"
    )
    run_reply(ChatRun.objects.get(run_type="agent", chat_id=created.conversation.id))
    return AgentMessage.objects.get(id=created.reply.id)


@pytest.mark.parametrize(
    "provider_type,model,supported",
    [
        ("openai", "gpt-5.1", True),
        ("anthropic", "claude-sonnet-4-5", True),
        ("google", "gemini-2.5-flash", True),
        # Groq retired its compound models, the only ones with web search.
        ("groq", "groq/compound", False),
        ("groq", "compound-beta", False),
        ("groq", "llama-3.3-70b-versatile", False),
        ("openrouter", "openai/gpt-5.1", False),
        ("xai", "grok-4", False),
        ("zai", "glm-4.6", False),
        ("bedrock", "anthropic.claude-sonnet-4-5", False),
        ("mistral", "mistral-large-latest", False),
        ("ollama", "llama3", False),
    ],
)
def test_providers_offer_web_search_for_supported_models(
    provider_type, model, supported
):
    model_type = generative_ai_model_type_registry.get(provider_type)

    assert (model_type.get_web_search_tool(model, False) is not None) is supported


def test_only_anthropic_caps_searches_itself():
    def max_uses(provider_type, model):
        model_type = generative_ai_model_type_registry.get(provider_type)
        return model_type.get_web_search_tool(model, False).max_uses

    assert max_uses("anthropic", "claude-sonnet-4-5") == 5
    assert max_uses("openai", "gpt-5.1") is None
    assert max_uses("google", "gemini-2.5-flash") is None


def test_anthropic_searches_without_running_code_to_filter_results():
    # Searches run from filtering code don't count against the reply's cap.
    model = generative_ai_model_type_registry.get("anthropic").get_ai_model(
        "claude-sonnet-5-5", settings_override={"api_key": "test-key"}
    )

    assert model.profile["anthropic_supports_dynamic_filtering"] is False


def agent_with_tools(configured_agent, user, provider_type, model):
    agent = configured_agent(
        user=user,
        provider_type=provider_type,
        model_identifier=model,
        web_search_enabled=True,
    )
    if provider_type != "openai":
        provider = AIProviderConfig.objects.create(
            workspace=agent.workspace, provider_type=provider_type, api_key="test-key"
        )
        AIProviderModel.objects.create(provider_config=provider, model_identifier=model)
    identity = Identity.objects.create(workspace=agent.workspace, name="Ops")
    AgentHandler().update_configuration(
        agent,
        run_as_subject_type="core.Agent",
        run_as_subject_id=identity.id,
        allowed_tools=["list_tables"],
    )
    return agent


def searches(count: int, first_index: int = 0) -> dict:
    parts = {}
    for number in range(count):
        tool_call_id = f"search-{first_index + number}"
        parts[first_index + 2 * number] = NativeToolCallPart(
            WebSearchTool.kind, args={"query": "q"}, tool_call_id=tool_call_id
        )
        parts[first_index + 2 * number + 1] = NativeToolReturnPart(
            WebSearchTool.kind, content=[], tool_call_id=tool_call_id
        )
    return parts


@pytest.mark.django_db
@pytest.mark.parametrize(
    "provider_type,model,first_searches,offered",
    [
        # Providers without a cap of their own stop getting search once the
        # reply used its searches.
        ("openai", "test-model", 5, None),
        ("openai", "test-model", 4, "no-cap"),
        # Anthropic counts the earlier searches of the reply against the same
        # cap, so a smaller one would refuse searches the reply still has.
        ("anthropic", "claude-sonnet-4-5", 3, WEB_SEARCH_MAX_PER_REPLY),
    ],
)
def test_searches_are_capped_across_a_whole_reply(
    mocker,
    data_fixture,
    configured_agent,
    provider_type,
    model,
    first_searches,
    offered,
):
    user = data_fixture.create_user()
    seen = []

    async def stream(messages, info):
        seen.append(info.model_request_parameters.native_tools)
        if len(seen) == 1:
            yield searches(first_searches)
            yield {
                2 * first_searches: DeltaToolCall(name="list_tables", json_args="{}")
            }
        else:
            yield "Done."

    use_stream(mocker, stream)

    reply = answer(user, agent_with_tools(configured_agent, user, provider_type, model))

    assert reply.status == "completed"
    assert len(seen) == 2
    assert len(seen[0]) == 1
    if offered is None:
        assert seen[1] == []
    else:
        assert len(seen[1]) == 1
        expected = None if offered == "no-cap" else offered
        assert seen[1][0].max_uses == expected


@pytest.mark.django_db
def test_search_left_waiting_by_a_tool_call_keeps_its_tool(
    mocker, data_fixture, configured_agent
):
    # Anthropic runs a search it emits next to a function tool call in the next
    # request, and rejects that request if the search tool is gone.
    user = data_fixture.create_user()
    seen = []

    async def stream(messages, info):
        seen.append(info.model_request_parameters.native_tools)
        if len(seen) == 1:
            yield searches(4)
            yield {
                8: NativeToolCallPart(
                    WebSearchTool.kind, args={"query": "q"}, tool_call_id="waiting"
                )
            }
            yield {9: DeltaToolCall(name="list_tables", json_args="{}")}
        else:
            yield "Done."

    use_stream(mocker, stream)

    reply = answer(
        user,
        agent_with_tools(configured_agent, user, "anthropic", "claude-sonnet-4-5"),
    )

    assert reply.status == "completed"
    assert len(seen[1]) == 1
    assert seen[1][0].max_uses == WEB_SEARCH_MAX_PER_REPLY


def ask_first_agent(
    data_fixture, configured_agent, user: AbstractUser
) -> tuple[AgentApplication, Table]:
    """An Agent that searches the web and asks before it creates rows."""

    agent = agent_with_tools(configured_agent, user, "openai", "test-model")
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(workspace=agent.workspace)
    )
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    AgentHandler().update_configuration(
        agent, allowed_tools=["create_rows"], ask_first_tools=["create_rows"]
    )
    return agent, table


def add_row(table: Table, index: int = 0) -> dict[int, DeltaToolCall]:
    return {
        index: DeltaToolCall(
            name="create_rows",
            json_args=f'{{"table_id": {table.id}, "rows": [{{"Name": "A"}}]}}',
        )
    }


def approve_and_resume(user: AbstractUser, reply: AgentMessage) -> AgentMessage:
    (approval,) = reply.approvals.all()
    conversation = reply.conversation
    _, run_id = AgentService().decide_approvals(
        user,
        conversation.agent_id,
        conversation.uuid,
        [{"id": approval.id, "approved": True}],
    )
    run_reply(ChatRun.objects.get(id=run_id))
    reply.refresh_from_db()
    return reply


@pytest.mark.django_db
def test_a_search_next_to_a_held_call_is_never_held_and_search_stays_on_resume(
    mocker, data_fixture, configured_agent
):
    user = data_fixture.create_user()
    agent, table = ask_first_agent(data_fixture, configured_agent, user)
    seen = []

    async def stream(messages, info):
        seen.append(info.model_request_parameters.native_tools)
        if len(seen) == 1:
            yield searches(1)
            yield add_row(table, 2)
        else:
            yield "Done."

    use_stream(mocker, stream)

    reply = answer(user, agent)

    assert reply.status == "waiting"
    assert [(step["tool"], step["status"]) for step in reply.steps] == [
        (WebSearchTool.kind, "done"),
        ("create_rows", "waiting"),
    ]
    reply = approve_and_resume(user, reply)
    assert reply.status == "completed"
    assert [step["status"] for step in reply.steps] == ["done", "done"]
    assert [len(tools) for tools in seen] == [1, 1]


@pytest.mark.django_db
@pytest.mark.parametrize("refused_by", ["provider", "sdk"])
def test_a_resumed_reply_never_offers_the_search_its_paused_run_could_not_use(
    mocker, data_fixture, configured_agent, refused_by
):
    user = data_fixture.create_user()
    agent, table = ask_first_agent(data_fixture, configured_agent, user)
    responses = iter([add_row(table), "Done."])

    async def stream(messages, info):
        if info.model_request_parameters.native_tools:
            raise ModelHTTPError(400, "test-model", body="web_search not supported")
        yield next(responses)

    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(
            FunctionModel(
                stream_function=stream,
                profile=ModelProfile(supported_native_tools=frozenset())
                if refused_by == "sdk"
                else None,
            ),
            {},
        ),
    )

    reply = approve_and_resume(user, answer(user, agent))

    assert (reply.status, reply.content) == ("completed", "Done.")
    assert [(step["tool"], step["status"]) for step in reply.steps] == [
        (WebSearchTool.kind, "failed"),
        ("create_rows", "done"),
    ]


def test_the_model_is_told_how_many_searches_a_reply_may_make():
    assert f"at most {WEB_SEARCH_MAX_PER_REPLY} times" in WEB_SEARCH_INSTRUCTIONS


def test_gemini_2_does_not_search_alongside_workspace_tools():
    google = generative_ai_model_type_registry.get("google")

    assert google.get_web_search_tool("gemini-2.5-flash", True) is None
    assert google.get_web_search_tool("gemini-2.5-flash", False) is not None
    assert google.get_web_search_tool("gemini-3-flash", True) is not None


@pytest.mark.django_db
def test_reply_on_gemini_2_with_tools_answers_without_search(
    mocker, data_fixture, configured_agent
):
    user = data_fixture.create_user()
    seen = []

    async def stream(messages, info):
        seen.append((info.model_request_parameters.native_tools, info.instructions))
        yield "ok"

    use_stream(mocker, stream)

    reply = answer(
        user, agent_with_tools(configured_agent, user, "google", "gemini-2.5-flash")
    )

    assert reply.status == "completed"
    assert seen[0][0] == []
    assert WEB_SEARCH_UNAVAILABLE_INSTRUCTIONS in seen[0][1]


@pytest.mark.django_db
def test_configuration_says_when_tools_block_search(data_fixture, configured_agent):
    user = data_fixture.create_user()
    agent = agent_with_tools(configured_agent, user, "google", "gemini-2.5-flash")

    configuration = AgentHandler().get_configuration(agent)

    assert configuration.web_search_available is False
    assert configuration.web_search_blocked_by_tools is True

    AgentHandler().update_configuration(agent, allowed_tools=[])
    configuration = AgentHandler().get_configuration(agent)
    assert configuration.web_search_available is True
    assert configuration.web_search_blocked_by_tools is False


def agent_with_only_mcp_tools(configured_agent, user, data_fixture):
    agent = agent_with_tools(configured_agent, user, "google", "gemini-2.5-flash")
    AgentHandler().update_configuration(agent, allowed_tools=[])
    server = data_fixture.create_mcp_server_integration(application=agent)
    MCPServerTool.objects.create(
        integration=server, name="search", definition_hash="x", enabled=True
    )
    return agent


@pytest.mark.django_db
def test_mcp_tools_block_search_like_workspace_tools(
    mocker, data_fixture, configured_agent
):
    user = data_fixture.create_user()
    agent = agent_with_only_mcp_tools(configured_agent, user, data_fixture)
    seen = []

    async def stream(messages, info):
        seen.append(info.model_request_parameters.native_tools)
        yield "ok"

    use_stream(mocker, stream)

    configuration = AgentHandler().get_configuration(agent)
    assert configuration.web_search_available is False
    assert configuration.web_search_blocked_by_tools is True
    assert answer(user, agent).status == "completed"
    assert seen[0] == []


@pytest.mark.django_db
def test_web_search_starts_off_and_is_available_only_with_a_supported_model(
    configured_agent,
):
    agent = configured_agent()
    configuration = AgentHandler().get_configuration(agent)
    assert configuration.web_search_enabled is False
    assert configuration.web_search_available is True

    agent.provider_type = "mistral"
    assert AgentHandler().get_configuration(agent).web_search_available is False

    agent.provider_type = None
    assert AgentHandler().get_configuration(agent).web_search_available is False

    agent.provider_type = "no-longer-registered"
    assert AgentHandler().get_configuration(agent).web_search_available is False


@pytest.mark.django_db
def test_new_agents_do_not_get_web_search_with_the_read_only_tools(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    agent = CoreHandler().create_application(user, workspace, "agent", name="A")

    configuration = AgentHandler().get_configuration(agent)
    assert configuration.web_search_enabled is False
    assert "web_search" not in configuration.allowed_tools


@pytest.mark.django_db
def test_web_search_setting_is_saved_through_the_api(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    agent = data_fixture.create_agent_application(user=user)

    response = api_client.patch(
        agent_url(agent, "configuration"),
        {"web_search_enabled": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 200, response.json()
    assert response.json()["web_search_enabled"] is True
    assert response.json()["web_search_available"] is False
    response = api_client.get(
        agent_url(agent, "configuration"), HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.json()["web_search_enabled"] is True


@pytest.mark.django_db
def test_changing_web_search_is_audited(mocker, data_fixture, configured_agent):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    registered = mocker.patch(
        "baserow.contrib.agent.actions.UpdateAgentConfigurationActionType.register_action"
    )

    UpdateAgentConfigurationActionType.do(user, agent.id, web_search_enabled=True)

    agent.refresh_from_db()
    assert agent.web_search_enabled is True
    params = registered.call_args.args[1]
    assert params.original_values["web_search_enabled"] is False
    assert params.new_values["web_search_enabled"] is True


@pytest.mark.django_db
def test_reply_offers_web_search_only_when_turned_on_for_a_supported_model(
    mocker, data_fixture, configured_agent
):
    user = data_fixture.create_user()
    seen = []

    async def stream(messages, info):
        seen.append((info.model_request_parameters.native_tools, info.instructions))
        yield "ok"

    use_stream(mocker, stream)

    answer(user, configured_agent(user=user))
    native_tools, instructions = seen[-1]
    assert native_tools == []
    assert WEB_SEARCH_INSTRUCTIONS not in instructions

    answer(user, configured_agent(user=user, web_search_enabled=True))
    native_tools, instructions = seen[-1]
    assert [tool.kind for tool in native_tools] == [WebSearchTool.kind]
    assert WEB_SEARCH_INSTRUCTIONS in instructions
    assert WEB_SEARCH_UNAVAILABLE_INSTRUCTIONS not in instructions


@pytest.mark.django_db
def test_reply_without_search_says_so_when_the_model_changed_to_an_unsupported_one(
    mocker, data_fixture
):
    user = data_fixture.create_user()
    agent = data_fixture.create_agent_application(
        user=user,
        instructions="Help.",
        provider_type="mistral",
        model_identifier="test-model",
        web_search_enabled=True,
    )
    seen = []

    async def stream(messages, info):
        seen.append((info.model_request_parameters.native_tools, info.instructions))
        yield "ok"

    use_stream(mocker, stream)
    mocker.patch(
        "baserow.contrib.agent.handler.AgentHandler.get_configuration_readiness",
        return_value=("ready", {}),
    )

    answer(user, agent)

    native_tools, instructions = seen[-1]
    assert native_tools == []
    assert WEB_SEARCH_UNAVAILABLE_INSTRUCTIONS in instructions
    agent.refresh_from_db()
    assert agent.web_search_enabled is True


@pytest.mark.django_db
def test_web_search_appears_as_a_step(mocker, data_fixture, configured_agent):
    user = data_fixture.create_user()

    async def stream(messages, info):
        yield {0: CALL}
        yield {1: RESULT}
        yield "The answer."

    use_stream(mocker, stream)

    reply = answer(user, configured_agent(user=user, web_search_enabled=True))

    assert reply.content == "The answer."
    assert [(step["tool"], step["status"], step["input"]) for step in reply.steps] == [
        (WebSearchTool.kind, "done", {"queries": ["baserow"]})
    ]
    assert reply.steps[0]["changes_data"] is False


@pytest.mark.django_db
def test_code_the_provider_runs_to_filter_results_is_not_a_step(
    mocker, data_fixture, configured_agent
):
    user = data_fixture.create_user()

    async def stream(messages, info):
        yield {0: NativeToolCallPart("code_execution", tool_call_id="code-1")}
        yield {1: CALL}
        yield {2: RESULT}
        yield {
            3: NativeToolReturnPart("code_execution", {}, tool_call_id="code-1"),
        }
        yield "The answer."

    use_stream(mocker, stream)

    reply = answer(user, configured_agent(user=user, web_search_enabled=True))

    assert reply.content == "The answer."
    assert [step["tool"] for step in reply.steps] == [WebSearchTool.kind]


def test_step_starts_when_the_search_does_and_learns_the_query_when_it_arrives():
    journal = Mock()
    responder = AgentResponder(
        Mock(allowed_tool_names=[], mcp_servers=(), resume=None), journal, Mock(), {}
    )
    started = NativeToolCallPart(WebSearchTool.kind, tool_call_id="search-1")

    responder._on_event(PartStartEvent(index=0, part=started))
    assert journal.emit.call_args.args[1]["status"] == "running"
    assert journal.emit.call_args.args[1]["input"] == {}

    responder._on_event(PartEndEvent(index=0, part=CALL))
    assert journal.emit.call_args.args[1]["status"] == "running"
    assert journal.emit.call_args.args[1]["input"] == {"queries": ["baserow"]}

    responder._on_event(PartStartEvent(index=1, part=RESULT))
    assert journal.emit.call_args.args[1]["status"] == "done"
    assert journal.emit.call_args.args[1]["input"] == {"queries": ["baserow"]}


def test_text_before_a_search_leaves_the_stream_once_the_answer_starts():
    journal = Mock()
    responder = AgentResponder(
        Mock(allowed_tool_names=[], mcp_servers=(), resume=None), journal, Mock(), {}
    )

    for index, part in enumerate(
        [TextPart("Let me look that up."), CALL, RESULT, TextPart("The answer")]
    ):
        responder._on_event(PartStartEvent(index=index, part=part))
    responder._on_event(PartDeltaEvent(index=3, delta=TextPartDelta(content_delta=".")))

    assert [call.args[0] for call in journal.emit_text.call_args_list] == [
        "Let me look that up.",
        "The answer",
        "The answer.",
    ]


def test_text_before_a_search_whose_result_arrives_late_leaves_the_stream():
    journal = Mock()
    responder = AgentResponder(
        Mock(allowed_tool_names=[], mcp_servers=(), resume=None), journal, Mock(), {}
    )

    for index, part in enumerate(
        [TextPart("Let me look. "), CALL, TextPart("Answer.")]
    ):
        responder._on_event(PartStartEvent(index=index, part=part))

    assert responder._text == "Answer."


@pytest.mark.django_db
def test_searches_reported_after_the_text_keep_the_streamed_answer(
    mocker, data_fixture, configured_agent
):
    user = data_fixture.create_user()
    streamed = []

    async def stream(messages, info):
        yield "Grounded answer."
        yield {1: CALL}
        yield {2: RESULT}

    use_stream(mocker, stream)
    mocker.patch(
        "baserow.core.chat_runs.journal.ChatRunJournal.emit_text",
        side_effect=streamed.append,
    )

    reply = answer(user, configured_agent(user=user, web_search_enabled=True))

    assert streamed[-1] == "Grounded answer."
    assert reply.content == "Grounded answer."
    assert reply.steps[0]["status"] == "done"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "content,outcome",
    [
        ({"error": "unavailable"}, "failed"),
        # Anthropic reports errors inside a successful result.
        (
            {"type": "web_search_tool_result_error", "error_code": "max_uses_exceeded"},
            "success",
        ),
        # OpenAI reports a failed search only through its status.
        ({"status": "failed"}, "success"),
    ],
)
def test_failed_search_shows_as_a_failed_step(
    mocker, data_fixture, configured_agent, content, outcome
):
    user = data_fixture.create_user()

    async def stream(messages, info):
        yield {0: CALL}
        yield {
            1: NativeToolReturnPart(
                tool_name=WebSearchTool.kind,
                content=content,
                tool_call_id="search-1",
                outcome=outcome,
            )
        }
        yield "Could not search."

    use_stream(mocker, stream)

    reply = answer(user, configured_agent(user=user, web_search_enabled=True))

    assert reply.content == "Could not search."
    assert reply.steps[0]["status"] == "failed"
    assert reply.steps[0]["error_code"] == "failed"


@pytest.mark.django_db
def test_completed_openai_search_shows_as_done(mocker, data_fixture, configured_agent):
    user = data_fixture.create_user()

    async def stream(messages, info):
        yield {0: CALL}
        yield {
            1: NativeToolReturnPart(
                tool_name=WebSearchTool.kind,
                content={"status": "completed", "sources": []},
                tool_call_id="search-1",
            )
        }
        yield "Found it."

    use_stream(mocker, stream)

    reply = answer(user, configured_agent(user=user, web_search_enabled=True))

    assert reply.steps[0]["status"] == "done"


@pytest.mark.django_db
def test_query_shown_in_a_step_is_limited_and_must_be_text(
    mocker, data_fixture, configured_agent
):
    user = data_fixture.create_user()

    async def stream(messages, info):
        yield {
            0: NativeToolCallPart(
                tool_name=WebSearchTool.kind,
                args={"query": "x" * 2000},
                tool_call_id="a",
            )
        }
        yield {1: NativeToolReturnPart(WebSearchTool.kind, [], tool_call_id="a")}
        yield {
            2: NativeToolCallPart(
                tool_name=WebSearchTool.kind, args={"query": 42}, tool_call_id="b"
            )
        }
        yield {3: NativeToolReturnPart(WebSearchTool.kind, [], tool_call_id="b")}
        yield {
            4: NativeToolCallPart(
                tool_name=WebSearchTool.kind,
                args={"queries": ["first", "second"]},
                tool_call_id="c",
            )
        }
        yield {5: NativeToolReturnPart(WebSearchTool.kind, [], tool_call_id="c")}
        yield "ok"

    use_stream(mocker, stream)

    reply = answer(user, configured_agent(user=user, web_search_enabled=True))

    first, second, third = reply.steps
    assert len(first["input"]["queries"][0]) == 512
    assert second["input"] == {}
    assert third["input"] == {"queries": ["first", "second"]}


@pytest.mark.parametrize(
    "arguments,step_input",
    [
        # OpenAI reports a query next to the queries it ran.
        ({"query": "q", "queries": ["a", "q", "b"]}, {"queries": ["q", "a", "b"]}),
        (
            {"queries": [f"q{number}" for number in range(9)]},
            {"queries": [f"q{number}" for number in range(5)]},
        ),
        ({"query": "", "queries": ["a"]}, {"queries": ["a"]}),
        ({"query": "", "queries": []}, {}),
        ({"queries": "not a list"}, {}),
        # A page the provider opened is what a steered agent would leak through.
        (
            {"type": "open_page", "url": "https://example.com/?d=x"},
            {"url": "https://example.com/?d=x"},
        ),
        ({"type": "open_page", "url": 42}, {}),
    ],
)
def test_search_steps_show_every_query_and_opened_page(arguments, step_input):
    assert _web_search_step_input(arguments) == step_input


@pytest.mark.django_db
def test_rejected_search_retries_once_without_it_and_says_so(
    mocker, data_fixture, configured_agent
):
    user = data_fixture.create_user()
    seen = []

    async def stream(messages, info):
        seen.append((info.model_request_parameters.native_tools, info.instructions))
        if info.model_request_parameters.native_tools:
            raise ModelHTTPError(400, "m", body="web_search not supported")
        yield "Without search."

    use_stream(mocker, stream)

    reply = answer(user, configured_agent(user=user, web_search_enabled=True))

    assert (reply.status, reply.content) == ("completed", "Without search.")
    assert len(seen) == 2
    assert seen[1][0] == []
    # A 400 doesn't prove the model can't search, so the model isn't told it
    # can't, and the reply shows that search was unavailable.
    assert WEB_SEARCH_FAILED_INSTRUCTIONS in seen[1][1]
    assert WEB_SEARCH_UNAVAILABLE_INSTRUCTIONS not in seen[1][1]
    assert WEB_SEARCH_INSTRUCTIONS not in seen[1][1]
    assert [(step["tool"], step["status"], step["input"]) for step in reply.steps] == [
        (WebSearchTool.kind, "failed", {"unavailable": True})
    ]


@pytest.mark.django_db
def test_model_whose_sdk_excludes_search_answers_without_it(
    mocker, data_fixture, configured_agent
):
    user = data_fixture.create_user()
    seen = []

    async def stream(messages, info):
        seen.append((info.model_request_parameters.native_tools, info.instructions))
        yield "Without search."

    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(
            FunctionModel(
                stream_function=stream,
                profile=ModelProfile(supported_native_tools=frozenset()),
            ),
            {},
        ),
    )

    reply = answer(user, configured_agent(user=user, web_search_enabled=True))

    assert (reply.status, reply.content) == ("completed", "Without search.")
    native_tools, instructions = seen[0]
    assert native_tools == []
    assert WEB_SEARCH_FAILED_INSTRUCTIONS in instructions
    assert WEB_SEARCH_INSTRUCTIONS not in instructions
    assert reply.steps[0]["input"] == {"unavailable": True}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "enabled,status_code,calls",
    [
        # Without search there is nothing to take out of the request.
        (False, 400, 1),
        # Only a rejected request means no search ran and nothing was charged.
        (True, 429, 1),
        (True, 500, 1),
    ],
)
def test_other_failures_are_not_retried(
    mocker, data_fixture, configured_agent, enabled, status_code, calls
):
    user = data_fixture.create_user()
    seen = []

    async def stream(messages, info):
        seen.append(1)
        raise ModelHTTPError(status_code, "m", body="details")
        yield "never"

    use_stream(mocker, stream)

    reply = answer(user, configured_agent(user=user, web_search_enabled=enabled))

    assert reply.status == "failed"
    assert len(seen) == calls


@pytest.mark.django_db
def test_failure_after_a_search_started_is_not_retried(
    mocker, data_fixture, configured_agent
):
    user = data_fixture.create_user()
    seen = []

    async def stream(messages, info):
        seen.append(1)
        yield {0: CALL}
        raise ModelHTTPError(400, "m", body="details")

    use_stream(mocker, stream)

    reply = answer(user, configured_agent(user=user, web_search_enabled=True))

    assert reply.status == "failed"
    assert len(seen) == 1


@pytest.mark.django_db
def test_failure_after_hidden_provider_code_started_is_not_retried(
    mocker, data_fixture, configured_agent
):
    user = data_fixture.create_user()
    seen = []

    async def stream(messages, info):
        seen.append(1)
        yield {0: NativeToolCallPart("code_execution", tool_call_id="code-1")}
        raise ModelHTTPError(400, "m", body="details")

    use_stream(mocker, stream)

    reply = answer(user, configured_agent(user=user, web_search_enabled=True))

    assert reply.status == "failed"
    assert not reply.steps
    assert len(seen) == 1


@pytest.mark.django_db
def test_copies_keep_web_search_and_imports_from_elsewhere_turn_it_off(
    data_fixture, configured_agent
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user, web_search_enabled=True)
    workspace = data_fixture.create_workspace(user=user)
    config = ImportExportConfig(include_permission_data=False)
    application_type = AgentApplicationType()

    assert CoreHandler().duplicate_application(user, agent).specific.web_search_enabled

    serialized = application_type.export_serialized(agent, config)
    assert serialized["web_search_enabled"] is True
    imported = application_type.import_serialized(workspace, serialized, config, {})
    assert imported.web_search_enabled is False


@pytest.mark.django_db
def test_templates_turn_web_search_off(data_fixture, configured_agent):
    user = data_fixture.create_user()
    agent = configured_agent(user=user, web_search_enabled=True)
    workspace = data_fixture.create_workspace(user=user)
    config = ImportExportConfig(
        include_permission_data=False, is_duplicate=True, is_template=True
    )
    application_type = AgentApplicationType()

    serialized = application_type.export_serialized(agent, config)
    imported = application_type.import_serialized(workspace, serialized, config, {})

    assert imported.web_search_enabled is False
