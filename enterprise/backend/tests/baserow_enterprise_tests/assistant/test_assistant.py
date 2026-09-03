import asyncio
import json
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any
from unittest.mock import MagicMock, patch

from django.test.utils import override_settings

import pytest
from asgiref.sync import async_to_sync
from pydantic_ai import ModelRetry
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    PartStartEvent,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.run import AgentRunResultEvent

from baserow_enterprise.assistant.action_memory import (
    MAX_VERIFIED_TOOL_OUTCOMES_CHARS,
    get_mutation_evidence,
    get_verified_tool_outcomes,
)
from baserow_enterprise.assistant.agents import (
    dynamic_license_tier,
    dynamic_verified_tool_outcomes,
)
from baserow_enterprise.assistant.assistant import (
    Assistant,
    _get_workspace_license_type,
)
from baserow_enterprise.assistant.deps import AssistantDeps
from baserow_enterprise.assistant.history import compact_message_history
from baserow_enterprise.assistant.model_profiles import get_model_string
from baserow_enterprise.assistant.models import (
    AssistantChat,
    AssistantChatMessage,
)
from baserow_enterprise.assistant.output_validation import validate_final_answer
from baserow_enterprise.assistant.prompts import AGENT_SYSTEM_PROMPT
from baserow_enterprise.assistant.types import (
    AiMessage,
    AiMessageChunk,
    AiStartedMessage,
    AiThinkingMessage,
    ApplicationUIContext,
    ChatTitleMessage,
    HumanMessage,
    TableUIContext,
    UIContext,
    UserUIContext,
    ViewUIContext,
    WorkspaceUIContext,
)

TEST_MODEL = "groq:test-model"


def _mutation_messages(
    tool_name: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
    call_id: str,
) -> list[ModelMessage]:
    return [
        ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name=tool_name,
                    args=arguments,
                    tool_call_id=call_id,
                )
            ]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name=tool_name,
                    content=result,
                    tool_call_id=call_id,
                )
            ]
        ),
    ]


@pytest.fixture(autouse=True)
def mock_posthog():
    with patch("baserow_enterprise.assistant.telemetry.get_posthog_client") as mock:
        mock.return_value = MagicMock()
        yield mock


@pytest.fixture(autouse=True)
def _set_test_model(settings):
    settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL = "groq/test-model"


# ---------------------------------------------------------------------------
# Mock helpers for pydantic-ai's run_stream_events async generator
# ---------------------------------------------------------------------------


async def _mock_run_stream_events(
    answer: str, messages_json: bytes = b"[]"
) -> AsyncIterator[Any]:
    """
    Async generator that mimics the events pulled from ``main_agent.run_stream_events()``,
    yielding PartStartEvent, then AgentRunResultEvent.
    """

    # Emit a text part start with the full answer
    yield PartStartEvent(index=0, part=TextPart(content=answer))

    # Emit the final result event
    mock_result = MagicMock()
    mock_result.output = answer
    mock_result.all_messages_json.return_value = messages_json
    yield AgentRunResultEvent(result=mock_result)


@asynccontextmanager
async def _mock_run_stream_events_cm(
    events: AsyncIterator[Any],
) -> AsyncIterator[AsyncIterator[Any]]:
    """run_stream_events() is a context manager yielding an iterator, so the double must be too."""

    yield events


def make_mock_run_stream_events_side_effect(
    answer: str, messages_json: bytes = b"[]"
) -> Callable[..., AbstractAsyncContextManager[AsyncIterator[Any]]]:
    """Return a side_effect callable returning the context manager run_stream_events() now yields."""

    def side_effect(
        *args: Any, **kwargs: Any
    ) -> AbstractAsyncContextManager[AsyncIterator[Any]]:
        return _mock_run_stream_events_cm(
            _mock_run_stream_events(answer, messages_json)
        )

    return side_effect


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAssistantDeps:
    """Test the AssistantDeps class for source tracking."""

    def test_extend_sources_deduplicates(self):
        deps = AssistantDeps(
            user=MagicMock(),
            workspace=MagicMock(),
            tool_helpers=MagicMock(),
        )

        deps.extend_sources(["https://example.com/doc1", "https://example.com/doc2"])
        assert deps.sources == [
            "https://example.com/doc1",
            "https://example.com/doc2",
        ]

        deps.extend_sources(["https://example.com/doc2", "https://example.com/doc3"])

        assert deps.sources == [
            "https://example.com/doc1",
            "https://example.com/doc2",
            "https://example.com/doc3",
        ]

    def test_extend_sources_preserves_order(self):
        deps = AssistantDeps(
            user=MagicMock(),
            workspace=MagicMock(),
            tool_helpers=MagicMock(),
        )

        deps.extend_sources(["https://example.com/a"])
        deps.extend_sources(["https://example.com/b"])
        deps.extend_sources(["https://example.com/a"])

        assert deps.sources == ["https://example.com/a", "https://example.com/b"]


@pytest.mark.django_db
class TestAssistantChatHistory:
    """Test chat history loading and formatting."""

    def test_list_chat_messages_returns_in_chronological_order(
        self, enterprise_data_fixture
    ):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        AssistantChatMessage.objects.create(
            chat=chat, role=AssistantChatMessage.Role.HUMAN, content="First question"
        )
        AssistantChatMessage.objects.create(
            chat=chat, role=AssistantChatMessage.Role.AI, content="First answer"
        )
        msg3 = AssistantChatMessage.objects.create(
            chat=chat, role=AssistantChatMessage.Role.HUMAN, content="Second question"
        )

        assistant = Assistant(chat)
        messages = assistant.list_chat_messages()

        assert len(messages) == 3
        assert messages[0].content == "First question"
        assert messages[1].content == "First answer"
        assert messages[2].content == "Second question"

        messages = assistant.list_chat_messages(last_message_id=msg3.id, limit=1)
        assert len(messages) == 1
        assert messages[0].content == "First answer"

    def test_load_message_history_returns_none_for_empty(self, enterprise_data_fixture):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        assistant = Assistant(chat)
        history = async_to_sync(assistant._load_message_history)()
        assert history is None

    def test_load_message_history_deserializes_and_compacts(
        self, enterprise_data_fixture
    ):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        messages = [
            ModelRequest(parts=[UserPromptPart(content="create a database")]),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="create_tables",
                        args={
                            "database_id": 41,
                            "thought": "creating",
                            "tables": [{"name": "Recipes"}],
                        },
                        tool_call_id="tc1",
                    )
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="create_tables",
                        content={"created_tables": [{"id": 73, "name": "Recipes"}]},
                        tool_call_id="tc1",
                    )
                ]
            ),
            ModelResponse(parts=[TextPart(content="Done!")]),
        ]
        chat.message_history = ModelMessagesTypeAdapter.dump_json(messages)
        chat.save(update_fields=["message_history"])

        assistant = Assistant(chat)
        history = async_to_sync(assistant._load_message_history)()

        assert history is not None
        assert len(history) == 2
        assert isinstance(history[0], ModelRequest)
        assert isinstance(history[1], ModelResponse)
        assert assistant._deps.verified_tool_outcomes[0]["result"] == {
            "created_tables": [{"id": 73, "name": "Recipes"}]
        }

        # API requests construct a new Assistant each turn. The next instance
        # must recover the same verified IDs from the chat blob.
        next_assistant = Assistant(chat)
        next_history = async_to_sync(next_assistant._load_message_history)()
        assert next_history is not None
        assert next_assistant._deps.verified_tool_outcomes == (
            assistant._deps.verified_tool_outcomes
        )

    def test_load_message_history_handles_corrupt_data(self, enterprise_data_fixture):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        chat.message_history = b"not valid json"
        chat.save(update_fields=["message_history"])

        assistant = Assistant(chat)
        history = async_to_sync(assistant._load_message_history)()
        assert history is None


class TestCompactMessageHistory:
    """Test the message history compaction logic."""

    def test_compacts_tool_calls_in_older_turns(self):
        messages = [
            ModelRequest(parts=[UserPromptPart(content="create a database")]),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="create_tables",
                        args={"thought": "creating"},
                        tool_call_id="tc1",
                    )
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="create_tables",
                        content="Created",
                        tool_call_id="tc1",
                    )
                ]
            ),
            ModelResponse(parts=[TextPart(content="Done!")]),
            ModelRequest(parts=[UserPromptPart(content="add a field")]),
            ModelResponse(parts=[TextPart(content="Added!")]),
        ]

        compacted = compact_message_history(messages)
        assert len(compacted) == 4

    def test_retains_bounded_verified_mutation_outcomes(self):
        messages = [
            ModelRequest(parts=[UserPromptPart(content="create an orders table")]),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="create_tables",
                        args={
                            "database_id": 41,
                            "tables": [{"name": "Orders"}],
                            "thought": "Creating the table",
                        },
                        tool_call_id="tc1",
                    )
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="create_tables",
                        content={
                            "created_tables": [
                                {
                                    "id": 73,
                                    "name": "Orders",
                                    "fields": [
                                        {
                                            "id": 92,
                                            "name": "Status",
                                            "type": "single_select",
                                        }
                                    ],
                                }
                            ]
                        },
                        tool_call_id="tc1",
                    )
                ]
            ),
            ModelResponse(parts=[TextPart(content="Created it.")]),
        ]

        compacted = compact_message_history(messages)
        outcomes = get_verified_tool_outcomes(compacted)

        assert len(compacted) == 2
        assert len(outcomes) == 1
        assert len(outcomes[0]["_request_fingerprint"]) == 64
        assert {
            key: value
            for key, value in outcomes[0].items()
            if key != "_request_fingerprint"
        } == {
            "tool": "create_tables",
            "arguments": {
                "database_id": 41,
                "tables": [{"name": "Orders"}],
            },
            "result": {
                "created_tables": [
                    {
                        "id": 73,
                        "name": "Orders",
                        "fields": [
                            {
                                "id": 92,
                                "name": "Status",
                                "type": "single_select",
                            }
                        ],
                    }
                ]
            },
            "changed": True,
            "completed": True,
            "failed": False,
        }

        # The metadata must survive another compaction cycle unchanged.
        round_tripped = ModelMessagesTypeAdapter.validate_json(
            ModelMessagesTypeAdapter.dump_json(compacted)
        )
        next_cycle = compact_message_history(
            [
                *round_tripped,
                ModelRequest(parts=[UserPromptPart(content="ok")]),
                ModelResponse(parts=[TextPart(content="Continuing.")]),
            ]
        )
        assert get_verified_tool_outcomes(next_cycle) == outcomes

    def test_remembers_failed_mutations_as_incomplete_work(self):
        messages = [
            ModelRequest(parts=[UserPromptPart(content="create it")]),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="create_builders",
                        args={"builders": [{"name": "Restaurant"}]},
                        tool_call_id="failed-1",
                    )
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="create_builders",
                        content={
                            "created_builders": [],
                            "error": "Permission denied",
                        },
                        tool_call_id="failed-1",
                    )
                ]
            ),
            ModelResponse(parts=[TextPart(content="It failed.")]),
        ]

        outcomes = get_verified_tool_outcomes(compact_message_history(messages))

        assert len(outcomes) == 1
        assert outcomes[0]["changed"] is False
        assert outcomes[0]["completed"] is False
        assert outcomes[0]["failed"] is True

    def test_verified_workflow_outcome_keeps_deep_field_values(self):
        messages = [
            ModelRequest(parts=[UserPromptPart(content="automate orders")]),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="create_workflows",
                        args={
                            "automation_id": 5,
                            "workflows": [
                                {
                                    "name": "Process Orders",
                                    "nodes": [
                                        {
                                            "type": "update_row",
                                            "values": [
                                                {
                                                    "field_id": 9,
                                                    "value": "Processing",
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        },
                        tool_call_id="workflow-1",
                    )
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="create_workflows",
                        content={"created_workflows": [{"id": 7}]},
                        tool_call_id="workflow-1",
                    )
                ]
            ),
            ModelResponse(parts=[TextPart(content="Done")]),
        ]

        compacted = compact_message_history(messages)
        outcomes = get_verified_tool_outcomes(compacted)

        assert "Processing" in str(outcomes)

    def test_verified_mutation_ledger_is_capped(self):
        messages = []
        for index in range(20):
            call_id = f"create-{index}"
            messages.extend(
                [
                    ModelRequest(
                        parts=[UserPromptPart(content=f"create database {index}")]
                    ),
                    ModelResponse(
                        parts=[
                            ToolCallPart(
                                tool_name="create_builders",
                                args={"builders": [{"name": f"DB {index}"}]},
                                tool_call_id=call_id,
                            )
                        ]
                    ),
                    ModelRequest(
                        parts=[
                            ToolReturnPart(
                                tool_name="create_builders",
                                content={"created_builders": [{"id": index + 1}]},
                                tool_call_id=call_id,
                            )
                        ]
                    ),
                    ModelResponse(parts=[TextPart(content="Done")]),
                ]
            )

        outcomes = get_verified_tool_outcomes(compact_message_history(messages))

        assert len(outcomes) == 12
        assert outcomes[0]["result"] == {"created_builders": [{"id": 9}]}
        assert outcomes[-1]["result"] == {"created_builders": [{"id": 20}]}

    def test_action_fingerprints_use_complete_arguments(self):
        shared = [{"name": f"Shared {index}"} for index in range(12)]
        messages = []
        for index, final_name in enumerate(("First", "Second")):
            call_id = f"large-{index}"
            messages.extend(
                [
                    ModelRequest(parts=[UserPromptPart(content="create builders")]),
                    ModelResponse(
                        parts=[
                            ToolCallPart(
                                tool_name="create_builders",
                                args={"builders": [*shared, {"name": final_name}]},
                                tool_call_id=call_id,
                            )
                        ]
                    ),
                    ModelRequest(
                        parts=[
                            ToolReturnPart(
                                tool_name="create_builders",
                                content={"created_builders": [{"id": index + 1}]},
                                tool_call_id=call_id,
                            )
                        ]
                    ),
                    ModelResponse(parts=[TextPart(content="Done")]),
                ]
            )

        outcomes = get_verified_tool_outcomes(compact_message_history(messages))

        assert len(outcomes) == 2
        assert outcomes[0]["arguments"] == outcomes[1]["arguments"]
        assert (
            outcomes[0]["_request_fingerprint"] != (outcomes[1]["_request_fingerprint"])
        )

    def test_oversized_newest_mutation_is_truncated_to_verified_flags(self):
        workflows = [
            {
                "name": f"Process Orders {workflow_index}",
                "nodes": [
                    {
                        "ref": f"update-{workflow_index}-{node_index}",
                        "type": "update_row",
                        "values": [
                            {
                                "field_id": field_index + 1,
                                "value": "Processing " * 20,
                            }
                            for field_index in range(12)
                        ],
                    }
                    for node_index in range(12)
                ],
            }
            for workflow_index in range(12)
        ]
        messages = [
            ModelRequest(parts=[UserPromptPart(content="automate every order flow")]),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="create_workflows",
                        args={"automation_id": 5, "workflows": workflows},
                        tool_call_id="large-workflow",
                    )
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="create_workflows",
                        content={
                            "created_workflows": [
                                {"id": index + 100, "name": workflow["name"]}
                                for index, workflow in enumerate(workflows)
                            ]
                        },
                        tool_call_id="large-workflow",
                    )
                ]
            ),
            ModelResponse(parts=[TextPart(content="Done")]),
        ]

        compacted = compact_message_history(messages)
        outcomes = get_verified_tool_outcomes(compacted)
        evidence = get_mutation_evidence(compacted)

        assert len(outcomes) == 1
        assert outcomes[0]["tool"] == "create_workflows"
        assert outcomes[0]["_truncated"] is True
        assert evidence[0].changed is True
        assert evidence[0].completed is True
        assert (
            len(json.dumps(outcomes, separators=(",", ":")))
            <= MAX_VERIFIED_TOOL_OUTCOMES_CHARS
        )

    def test_compaction_preserves_partial_state(self):
        fields = [
            {"field_id": index, "name": f"Field {index} " + "x" * 200}
            for index in range(30)
        ]
        messages = [
            ModelRequest(parts=[UserPromptPart(content="update all fields")]),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="update_fields",
                        args={"fields": fields},
                        tool_call_id="partial-fields",
                    )
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="update_fields",
                        content={
                            "updated_fields": [
                                {"id": index, "name": "Updated " + "y" * 200}
                                for index in range(12)
                            ],
                            "errors": [
                                f"Field {index} could not be updated " + "z" * 200
                                for index in range(12, 24)
                            ],
                        },
                        tool_call_id="partial-fields",
                    )
                ]
            ),
            ModelResponse(parts=[TextPart(content="Partially updated")]),
        ]

        compacted = compact_message_history(messages)
        outcomes = get_verified_tool_outcomes(compacted)
        evidence = get_mutation_evidence(compacted)

        assert outcomes[0]["_truncated"] is True
        assert evidence[0].changed is True
        assert evidence[0].completed is False

    def test_identical_reused_retry_keeps_created_outcome(self):
        arguments = {"builders": [{"name": "Restaurant", "type": "database"}]}
        created = [
            ModelRequest(parts=[UserPromptPart(content="create Restaurant")]),
            *_mutation_messages(
                "create_builders",
                arguments,
                {
                    "created_builders": [
                        {"id": 1, "name": "Restaurant", "type": "database"}
                    ],
                    "reused_builders": [],
                },
                "created-builder",
            ),
            ModelResponse(parts=[TextPart(content="Done")]),
            ModelRequest(parts=[UserPromptPart(content="create Inventory")]),
            *_mutation_messages(
                "create_builders",
                {"builders": [{"name": "Inventory", "type": "database"}]},
                {
                    "created_builders": [
                        {"id": 2, "name": "Inventory", "type": "database"}
                    ],
                    "reused_builders": [],
                },
                "created-inventory",
            ),
            ModelResponse(parts=[TextPart(content="Done")]),
        ]
        first_compaction = compact_message_history(created)
        retried = [
            *first_compaction,
            ModelRequest(parts=[UserPromptPart(content="create Restaurant")]),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="create_builders",
                        args=arguments,
                        tool_call_id="reused-builder",
                    )
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="create_builders",
                        content={
                            "created_builders": [],
                            "reused_builders": [
                                {
                                    "id": 1,
                                    "name": "Restaurant",
                                    "type": "database",
                                }
                            ],
                        },
                        tool_call_id="reused-builder",
                    )
                ]
            ),
            ModelResponse(parts=[TextPart(content="Already exists")]),
        ]

        outcomes = get_verified_tool_outcomes(compact_message_history(retried))

        assert outcomes[-1]["changed"] is True
        assert outcomes[-1]["result"]["created_builders"][0]["name"] == "Restaurant"

    def test_compacted_failure_replaces_stale_success(self):
        arguments = {"database_id": 1, "tables": [{"name": "Orders"}]}
        created = [
            ModelRequest(parts=[UserPromptPart(content="create Orders")]),
            *_mutation_messages(
                "create_tables",
                arguments,
                {"created_tables": [{"id": 2, "name": "Orders"}]},
                "created-orders",
            ),
            ModelResponse(parts=[TextPart(content="Done")]),
        ]
        failed_retry = [
            *compact_message_history(created),
            ModelRequest(parts=[UserPromptPart(content="retry Orders")]),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="create_tables",
                        args=arguments,
                        tool_call_id="failed-orders",
                    )
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="create_tables",
                        content={
                            "created_tables": [],
                            "error": "Permission denied",
                        },
                        tool_call_id="failed-orders",
                    )
                ]
            ),
            ModelResponse(parts=[TextPart(content="It failed")]),
        ]
        compacted = compact_message_history(failed_retry)
        ctx = MagicMock(messages=compacted)

        outcomes = get_verified_tool_outcomes(compacted)
        assert outcomes[0]["failed"] is True
        with pytest.raises(ModelRetry, match="without a verified"):
            validate_final_answer(ctx, "I created the Orders table.")

    def test_trims_to_max_messages(self):
        messages = []
        for i in range(20):
            messages.append(
                ModelRequest(parts=[UserPromptPart(content=f"Question {i}")])
            )
            messages.append(ModelResponse(parts=[TextPart(content=f"Answer {i}")]))

        compacted = compact_message_history(messages, max_messages=6)
        assert len(compacted) == 6

    def test_preserves_simple_conversations(self):
        messages = [
            ModelRequest(parts=[UserPromptPart(content="hello")]),
            ModelResponse(parts=[TextPart(content="hi")]),
        ]

        compacted = compact_message_history(messages)
        assert len(compacted) == 2


@pytest.mark.django_db
class TestAssistantLicenseTier:
    @patch("baserow_enterprise.assistant.assistant._get_workspace_license_type")
    def test_assistant_initializes_license_tier(
        self, mock__get_workspace_license_type, enterprise_data_fixture
    ):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )
        license_type = MagicMock(type="premium", features=["premium"])
        mock__get_workspace_license_type.return_value = license_type

        assistant = Assistant(chat)

        mock__get_workspace_license_type.assert_called_once_with(user, workspace)
        assert assistant._deps.license_tier is license_type

    def test_dynamic_license_tier_injects_type_and_features(self):
        ctx = MagicMock()
        ctx.deps.license_tier = MagicMock(type="advanced", features=["sso", "rbac"])

        assert dynamic_license_tier(ctx) == (
            "\n<license_tier>advanced</license_tier>\n<features>rbac,sso</features>"
        )

    def test_dynamic_license_tier_normalizes_internal_enterprise_type(self):
        ctx = MagicMock()
        ctx.deps.license_tier = MagicMock(
            type="enterprise_without_support", features=["sso", "rbac"]
        )

        assert dynamic_license_tier(ctx) == (
            "\n<license_tier>enterprise</license_tier>\n<features>rbac,sso</features>"
        )

    def test_dynamic_license_tier_renders_free_for_unknown_type(self):
        ctx = MagicMock()
        ctx.deps.license_tier = MagicMock(type="unknown", features=["sso", "rbac"])

        assert dynamic_license_tier(ctx) == (
            "\n<license_tier>free</license_tier>\n<features>rbac,sso</features>"
        )

    def test_dynamic_license_tier_renders_free_when_no_license(self):
        ctx = MagicMock()
        ctx.deps.license_tier = None

        assert dynamic_license_tier(ctx) == "\n<license_tier>free</license_tier>"

    def test_agent_system_prompt_includes_grounding_guardrail(self):
        assert "Call `search_user_docs` first" in AGENT_SYSTEM_PROMPT
        assert "documentation search is not configured" in AGENT_SYSTEM_PROMPT
        assert "Never invent plan names" in AGENT_SYSTEM_PROMPT

    def test_agent_system_prompt_calibrates_asking_on_intent(self):
        """Asking is an action (ask_user), not the absence of one — the prompt
        must route the ask cases to the tool, or it competes with the
        agent's bias toward acting."""

        assert "<intent>" in AGENT_SYSTEM_PROMPT
        assert "Default to building" in AGENT_SYSTEM_PROMPT
        assert "never invent their data" in AGENT_SYSTEM_PROMPT
        assert "You act rather than describe" in AGENT_SYSTEM_PROMPT

    def test_agent_system_prompt_covers_production_regressions(self):
        assert "Cross-mode routing is automatic" in AGENT_SYSTEM_PROMPT
        assert "Use only real IDs returned by tools" in AGENT_SYSTEM_PROMPT
        assert "continue the latest unfinished request" in AGENT_SYSTEM_PROMPT
        assert (
            "Claim success only after a successful tool result" in AGENT_SYSTEM_PROMPT
        )
        assert "use generate_formula" in AGENT_SYSTEM_PROMPT

    def test_verified_outcomes_are_injected_as_facts_not_completion(self):
        ctx = MagicMock()
        ctx.deps.verified_tool_outcomes = [
            {"tool": "create_builders", "result": {"id": 42}}
        ]

        rendered = dynamic_verified_tool_outcomes(ctx)

        assert '"id":42' in rendered
        assert "do not prove the current request is complete" in rendered


@pytest.mark.django_db
class TestGetWorkspaceLicenseType:
    _PATCH_PATH = (
        "baserow_enterprise.assistant.assistant.ActiveLicensesDataType.get_user_data"
    )

    def _call(self, data, workspace_id=1):
        with patch(self._PATCH_PATH, return_value=data):
            return _get_workspace_license_type(MagicMock(), MagicMock(id=workspace_id))

    def test_returns_none_without_active_licenses(self):
        assert self._call({"instance_wide": {}, "per_workspace": {}}) is None

    def test_returns_instance_wide_license(self):
        result = self._call({"instance_wide": {"premium": True}, "per_workspace": {}})
        assert result is not None
        assert result.type == "premium"

    def test_returns_per_workspace_license(self):
        result = self._call(
            {"instance_wide": {}, "per_workspace": {42: {"advanced": True}}},
            workspace_id=42,
        )
        assert result is not None
        assert result.type == "advanced"

    def test_ignores_licenses_from_other_workspaces(self):
        assert (
            self._call(
                {"instance_wide": {}, "per_workspace": {99: {"advanced": True}}},
                workspace_id=42,
            )
            is None
        )

    def test_picks_highest_order_from_combined_set(self):
        result = self._call(
            {
                "instance_wide": {"premium": True},
                "per_workspace": {1: {"advanced": True}},
            }
        )
        assert result is not None
        # PremiumLicenseType.order=10, AdvancedLicenseType.order=75
        assert result.type == "advanced"

    def test_skips_license_names_not_in_registry(self):
        result = self._call(
            {
                "instance_wide": {"bogus_tier": True, "premium": True},
                "per_workspace": {},
            }
        )
        assert result is not None
        assert result.type == "premium"

    def test_returns_none_when_only_unknown_names(self):
        assert (
            self._call({"instance_wide": {"bogus_tier": True}, "per_workspace": {}})
            is None
        )


@pytest.mark.django_db
class TestAssistantMessagePersistence:
    """Test that messages are persisted correctly during streaming."""

    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_persists_human_message(
        self, mock_run_stream_events, enterprise_data_fixture
    ):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        mock_run_stream_events.side_effect = make_mock_run_stream_events_side_effect(
            "Hello"
        )

        assistant = Assistant(chat)
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
            user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
        )

        async def consume_stream():
            human_message = HumanMessage(content="Test message", ui_context=ui_context)
            async for _ in assistant.astream_messages(human_message):
                pass

        async_to_sync(consume_stream)()

        human_messages = AssistantChatMessage.objects.filter(
            chat=chat, role=AssistantChatMessage.Role.HUMAN
        ).count()
        assert human_messages == 1

        saved_message = AssistantChatMessage.objects.filter(
            chat=chat, role=AssistantChatMessage.Role.HUMAN
        ).first()
        assert saved_message.content == "Test message"

    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_persists_ai_message(
        self, mock_run_stream_events, enterprise_data_fixture
    ):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        mock_run_stream_events.side_effect = make_mock_run_stream_events_side_effect(
            "Based on docs"
        )

        assistant = Assistant(chat)
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
            user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
        )

        async def consume_stream():
            human_message = HumanMessage(content="Question", ui_context=ui_context)
            async for _ in assistant.astream_messages(human_message):
                pass

        async_to_sync(consume_stream)()

        ai_messages = AssistantChatMessage.objects.filter(
            chat=chat, role=AssistantChatMessage.Role.AI
        ).count()
        assert ai_messages == 1

    @patch("baserow_enterprise.assistant.agents.title_agent.run")
    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_persists_chat_title(
        self,
        mock_run_stream_events,
        mock_title_run,
        enterprise_data_fixture,
    ):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(user=user, workspace=workspace, title="")

        mock_run_stream_events.side_effect = make_mock_run_stream_events_side_effect(
            "Hello"
        )

        mock_title_result = MagicMock()
        mock_title_result.output = "Greeting"
        mock_title_run.return_value = mock_title_result

        assistant = Assistant(chat)
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
            user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
        )

        async def consume_stream():
            human_message = HumanMessage(content="Hello", ui_context=ui_context)
            async for _ in assistant.astream_messages(human_message):
                pass

        async_to_sync(consume_stream)()

        chat.refresh_from_db()
        assert chat.title == "Greeting"


@pytest.mark.django_db
class TestAssistantStreaming:
    """Test streaming behavior of the Assistant."""

    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_yields_answer_chunks(
        self, mock_run_stream_events, enterprise_data_fixture
    ):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        mock_run_stream_events.side_effect = make_mock_run_stream_events_side_effect(
            "Hello world"
        )

        assistant = Assistant(chat)

        async def consume_stream():
            messages = []
            human_message = HumanMessage(content="Test")
            async for msg in assistant.astream_messages(human_message):
                messages.append(msg)
            return messages

        messages = async_to_sync(consume_stream)()

        # Filter for final AiMessage
        ai_messages = [m for m in messages if isinstance(m, AiMessage)]
        assert len(ai_messages) == 1
        assert ai_messages[0].content == "Hello world"
        assert ai_messages[0].id is not None

        # Should also have AiMessageChunk(s)
        chunks = [
            m
            for m in messages
            if isinstance(m, AiMessageChunk) and not isinstance(m, AiMessage)
        ]
        assert len(chunks) >= 1

    @patch("baserow_enterprise.assistant.agents.title_agent.run")
    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_yields_title_for_new_chat(
        self, mock_run_stream_events, mock_title_run, enterprise_data_fixture
    ):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(user=user, workspace=workspace, title="")

        mock_run_stream_events.side_effect = make_mock_run_stream_events_side_effect(
            "Answer"
        )

        mock_title_result = MagicMock()
        mock_title_result.output = "Title"
        mock_title_run.return_value = mock_title_result

        assistant = Assistant(chat)

        async def consume_stream():
            msgs = []
            human_message = HumanMessage(content="Test")
            async for msg in assistant.astream_messages(human_message):
                msgs.append(msg)
            return msgs

        messages = async_to_sync(consume_stream)()

        title_messages = [m for m in messages if isinstance(m, ChatTitleMessage)]
        assert len(title_messages) == 1
        assert title_messages[0].content == "Title"

    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_yields_thinking_messages(
        self, mock_run_stream_events, enterprise_data_fixture
    ):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test Chat"
        )

        assistant = Assistant(chat)

        async def mock_stream_with_thinking(*args, **kwargs):
            # Emit thinking message via the event bus during streaming
            assistant._event_bus.emit(AiThinkingMessage(content="still thinking..."))

            # Yield text part then result
            yield PartStartEvent(index=0, part=TextPart(content="Answer"))

            mock_result = MagicMock()
            mock_result.output = "Answer"
            mock_result.all_messages_json.return_value = b"[]"
            yield AgentRunResultEvent(result=mock_result)

        mock_run_stream_events.side_effect = (
            lambda *args, **kwargs: _mock_run_stream_events_cm(
                mock_stream_with_thinking(*args, **kwargs)
            )
        )

        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
            user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
        )

        async def consume_stream():
            thinking = []
            human_message = HumanMessage(content="Test", ui_context=ui_context)
            async for msg in assistant.astream_messages(human_message):
                if isinstance(msg, AiThinkingMessage):
                    thinking.append(msg)
            return thinking

        thinking_messages = async_to_sync(consume_stream)()

        assert len(thinking_messages) == 1
        assert thinking_messages[0].content == "still thinking..."

    @patch("baserow_enterprise.assistant.agents.main_agent.run_stream_events")
    def test_astream_messages_yields_ai_started_message(
        self, mock_run_stream_events, enterprise_data_fixture
    ):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test"
        )

        mock_run_stream_events.side_effect = make_mock_run_stream_events_side_effect(
            "Hello"
        )

        assistant = Assistant(chat)
        human_message = HumanMessage(content="Hello")

        async def collect_messages():
            messages = []
            async for msg in assistant.astream_messages(human_message):
                messages.append(msg)
            return messages

        messages = async_to_sync(collect_messages)()

        assert len(messages) > 0
        assert isinstance(messages[0], AiStartedMessage)
        assert messages[0].message_id is not None


@pytest.mark.django_db
def test_stream_agent_run_drives_the_real_pydantic_ai_stream(enterprise_data_fixture):
    """
    Exercises main_agent.run_stream_events for real, unmocked.

    The other streaming tests patch run_stream_events with an async generator,
    which cannot detect a change in how that call must be invoked. This one
    fails if the call shape is wrong.
    """

    from pydantic_ai.models.test import TestModel

    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )
    assistant = Assistant(chat)
    queue = asyncio.Queue()

    async def run():
        return await assistant._stream_agent_run("say hello", None, queue)

    # call_tools=[]: TestModel's default 'all' would invoke every real tool with synthetic args.
    with patch.object(
        assistant, "_model", TestModel(custom_output_text="hello", call_tools=[])
    ):
        result = async_to_sync(run)()

    assert result is not None, "the real stream produced no AgentRunResultEvent"
    answer, run_result = result
    assert answer == "hello"
    assert run_result.all_messages_json()


@pytest.mark.django_db
def test_stream_agent_run_cancellation_propagates_through_async_with(
    enterprise_data_fixture,
):
    """
    Cancels the task driving ``_stream_agent_run`` mid-stream.

    ``_RunStreamEventsContext.__aexit__`` is only ever invoked by an ``async
    with`` block, so observing it fire on cancellation proves the
    cancellation unwound through that block.
    """

    from types import TracebackType

    from pydantic_ai.agent.abstract import _RunStreamEventsContext
    from pydantic_ai.models.function import AgentInfo, FunctionModel

    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    chat = AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )
    assistant = Assistant(chat)
    queue = asyncio.Queue()

    reached_block = asyncio.Event()

    async def stream_function(messages: list[ModelMessage], agent_info: AgentInfo):
        yield "partial answer"
        reached_block.set()
        await asyncio.Event().wait()  # never set: only cancellation ends this

    aexit_exc_types: list[type[BaseException] | None] = []
    real_aexit = _RunStreamEventsContext.__aexit__

    async def spy_aexit(
        self: _RunStreamEventsContext,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        aexit_exc_types.append(exc_type)
        return await real_aexit(self, exc_type, exc, tb)

    async def run_and_cancel() -> None:
        with (
            patch.object(
                assistant, "_model", FunctionModel(stream_function=stream_function)
            ),
            patch.object(_RunStreamEventsContext, "__aexit__", spy_aexit),
        ):
            task = asyncio.ensure_future(
                assistant._stream_agent_run("say hello", None, queue)
            )
            await reached_block.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    async_to_sync(run_and_cancel)()

    assert asyncio.CancelledError in aexit_exc_types, (
        "_RunStreamEventsContext.__aexit__ never ran with CancelledError — "
        "cancellation did not unwind through the async with block"
    )


@pytest.mark.django_db
class TestUIContext:
    """Test UI context handling and validation."""

    def test_ui_context_from_validate_request_adds_user_info(
        self, enterprise_data_fixture
    ):
        user = enterprise_data_fixture.create_user(
            email="test@example.com", first_name="Test User"
        )
        workspace = enterprise_data_fixture.create_workspace(user=user)

        class MockRequest:
            pass

        request = MockRequest()
        request.user = user

        ui_context_data = {"workspace": {"id": workspace.id, "name": workspace.name}}
        ui_context = UIContext.from_validate_request(request, ui_context_data)

        assert ui_context.workspace.id == workspace.id
        assert ui_context.workspace.name == workspace.name
        assert ui_context.user.id == user.id
        assert ui_context.user.email == "test@example.com"
        assert ui_context.user.name == "Test User"

    def test_ui_context_with_database_builder_fields(self):
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=1, name="Test Workspace"),
            database=ApplicationUIContext(id="db-123", name="My Database"),
            table=TableUIContext(id=456, name="Customers"),
            view=ViewUIContext(id=789, name="All Customers", type="grid"),
            user=UserUIContext(id=1, name="Test", email="test@test.com"),
        )

        assert ui_context.workspace.id == 1
        assert ui_context.database.id == "db-123"
        assert ui_context.table.id == 456
        assert ui_context.view.id == 789

    def test_ui_context_serialization_excludes_none_values(self):
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=1, name="Test Workspace"),
            user=UserUIContext(id=1, name="Test", email="test@test.com"),
        )

        serialized = ui_context.model_dump(exclude_none=True)
        assert "workspace" in serialized
        assert "user" in serialized
        assert "database" not in serialized
        assert "table" not in serialized

    def test_ui_context_has_default_timestamp(self):
        from datetime import datetime

        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=1, name="Test"),
            user=UserUIContext(id=1, name="Test", email="test@test.com"),
        )

        assert ui_context.timestamp is not None
        assert isinstance(ui_context.timestamp, datetime)

    def test_ui_context_has_default_timezone(self):
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=1, name="Test"),
            user=UserUIContext(id=1, name="Test", email="test@test.com"),
        )

        assert ui_context.timezone == "UTC"

    def test_user_ui_context_from_user(self, enterprise_data_fixture):
        user = enterprise_data_fixture.create_user(
            email="john@example.com", first_name="John Doe"
        )

        user_context = UserUIContext.from_user(user)

        assert user_context.id == user.id
        assert user_context.name == "John Doe"
        assert user_context.email == "john@example.com"

    def test_human_message_with_ui_context(self):
        ui_context = UIContext(
            workspace=WorkspaceUIContext(id=1, name="Test Workspace"),
            database=ApplicationUIContext(id="db-123", name="My Database"),
            user=UserUIContext(id=1, name="Test", email="test@test.com"),
        )

        human_message = HumanMessage(
            content="How do I create a field?", ui_context=ui_context
        )

        assert human_message.content == "How do I create a field?"
        assert human_message.ui_context.workspace.id == 1
        assert human_message.ui_context.database.id == "db-123"


@pytest.mark.django_db
class TestAssistantCancellation:
    """Test cancellation functionality in Assistant."""

    def test_get_cancellation_cache_key(self, enterprise_data_fixture):
        user = enterprise_data_fixture.create_user()
        workspace = enterprise_data_fixture.create_workspace(user=user)
        chat = AssistantChat.objects.create(
            user=user, workspace=workspace, title="Test"
        )

        from baserow_enterprise.assistant.assistant import (
            get_assistant_cancellation_key,
        )

        cache_key = get_assistant_cancellation_key(str(chat.uuid))
        assert cache_key == f"assistant:chat:{chat.uuid}:cancelled"


class TestGetModelString:
    """Test the model string conversion logic."""

    @override_settings(BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL="groq/llama-3.3-70b")
    def test_replaces_slash_with_colon(self):
        assert get_model_string() == "groq:llama-3.3-70b"

    @override_settings(BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL="openai/gpt-4")
    def test_openai_model(self):
        assert get_model_string() == "openai:gpt-4"

    @override_settings(BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL="gpt-4o")
    def test_bare_model_defaults_to_openai(self):
        assert get_model_string() == "openai:gpt-4o"

    def test_explicit_model_overrides_setting(self):
        assert get_model_string("groq/custom-model") == "groq:custom-model"

    def test_google_gla_prefix_is_normalised(self):
        """Sub-agents pass this string straight to pydantic-ai's infer_model,
        which only accepts its own provider names."""

        assert get_model_string("google-gla:gemini-2.0-flash") == (
            "google:gemini-2.0-flash"
        )

    def test_google_vertex_prefix_is_normalised(self):
        assert get_model_string("google-vertex:gemini-2.0-flash") == (
            "google-cloud:gemini-2.0-flash"
        )


class TestFinalAnswerValidation:
    def test_tool_call_printed_as_text_is_sent_back(self):
        payload = '{"name": "create_rows_in_table_9", "arguments": {"rows": []}}'
        with pytest.raises(ModelRetry):
            validate_final_answer(None, payload)

        fenced = f"```json\n{payload}\n```"
        with pytest.raises(ModelRetry):
            validate_final_answer(None, fenced)

        keys_reordered = '{"id": "c1", "name": "create_tables", "arguments": {}}'
        with pytest.raises(ModelRetry):
            validate_final_answer(None, keys_reordered)

    def test_regular_answers_pass_through(self):
        answer = 'Created the table. The field {"name": ...} maps to your schema.'
        assert validate_final_answer(None, answer) == answer
        availability = "The automation tools are available."
        assert validate_final_answer(None, availability) == availability

    def test_ungrounded_tool_unavailable_claim_is_sent_back(self):
        with pytest.raises(ModelRetry, match="current mode"):
            validate_final_answer(
                None,
                "The tools for building automations aren't available in this session.",
            )

    def test_truthful_tool_limitation_or_permission_explanation_is_allowed(self):
        limitation = (
            "The dashboard-creation tool isn't available because <limitations> "
            "explicitly excludes creating or modifying dashboards."
        )
        assert validate_final_answer(None, limitation) == limitation

        permission = (
            "I don't have access to the role-management tool because your role "
            "does not permit changing workspace permissions."
        )
        assert validate_final_answer(None, permission) == permission

    def test_ungrounded_success_claim_is_sent_back(self):
        ctx = MagicMock()
        ctx.messages = []
        with pytest.raises(ModelRetry, match="without a verified"):
            validate_final_answer(
                ctx, "The Restaurant database has been created successfully."
            )

        answer = "It already exists from the previous step."
        assert validate_final_answer(ctx, answer) == answer

        ctx.messages = [
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="create_rows_in_table_9",
                        args={"rows": [{"Name": "Order 12"}]},
                        tool_call_id="rows-1",
                    )
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="create_rows_in_table_9",
                        content={"created_rows": [{"id": 12}]},
                        tool_call_id="rows-1",
                    )
                ]
            ),
        ]
        completed = "I've created the requested rows successfully."
        assert validate_final_answer(ctx, completed) == completed

        rephrased = "I've updated the table with the requested rows."
        assert validate_final_answer(ctx, rephrased) == rephrased

    @pytest.mark.parametrize(
        "claim",
        [
            "Created the Orders table.",
            "I created the Orders table.",
            "Done — set up the workflow.",
            "Done.",
            "Applied the requested configuration.",
        ],
    )
    def test_common_ungrounded_completion_phrases_are_sent_back(self, claim):
        ctx = MagicMock()
        ctx.messages = []

        with pytest.raises(ModelRetry, match="without a verified"):
            validate_final_answer(ctx, claim)

    @pytest.mark.parametrize(
        "claim",
        [
            "I've created the text field 'Notes'.",
            "I've created a long text field called Notes.",
            "I created the Notes field successfully.",
        ],
    )
    def test_truthful_field_claims_with_matching_evidence_pass(self, claim):
        ctx = MagicMock()
        ctx.messages = _mutation_messages(
            "create_fields",
            {"table_id": 9, "fields": [{"name": "Notes", "type": "long_text"}]},
            {"created_fields": [{"id": 55, "name": "Notes", "type": "long_text"}]},
            "notes-field",
        )

        assert validate_final_answer(ctx, claim) == claim

    def test_truthful_view_claim_with_matching_evidence_passes(self):
        ctx = MagicMock()
        ctx.messages = _mutation_messages(
            "create_views",
            {"table_id": 9, "views": [{"name": "Intake", "type": "form"}]},
            {"created_views": [{"id": 7, "name": "Intake", "type": "form"}]},
            "form-view",
        )
        claim = "The form view has been created."

        assert validate_final_answer(ctx, claim) == claim

    def test_any_successful_mutation_grounds_a_differently_phrased_claim(self):
        ctx = MagicMock()
        ctx.messages = _mutation_messages(
            "update_fields",
            {"table_id": 9, "fields": [{"id": 55, "options": ["In Progress"]}]},
            {"updated_fields": [{"id": 55, "name": "Status"}]},
            "status-field",
        )
        claim = "I've added the In Progress option to the Status field."

        assert validate_final_answer(ctx, claim) == claim

    def test_completion_claim_can_use_multiple_matching_tool_results(self):
        ctx = MagicMock()
        ctx.messages = [
            *_mutation_messages(
                "create_builders",
                {"builders": [{"name": "Restaurant", "type": "database"}]},
                {"created_builders": [{"id": 1, "type": "database"}]},
                "database",
            ),
            *_mutation_messages(
                "create_tables",
                {"database_id": 1, "tables": [{"name": "Orders"}]},
                {"created_tables": [{"id": 2, "name": "Orders"}]},
                "table",
            ),
            *_mutation_messages(
                "create_workflows",
                {"automation_id": 3, "workflows": [{"name": "Process Orders"}]},
                {"created_workflows": [{"id": 4, "name": "Process Orders"}]},
                "workflow",
            ),
        ]
        answer = "I've created the database, table, and workflow successfully."

        assert validate_final_answer(ctx, answer) == answer

    def test_no_op_update_does_not_ground_success(self):
        ctx = MagicMock()
        ctx.messages = [
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="update_builder",
                        args={"builder_id": 1, "update": {}},
                        tool_call_id="update",
                    )
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="update_builder",
                        content={"id": 1, "name": "Restaurant", "changed": False},
                        tool_call_id="update",
                    )
                ]
            ),
        ]

        with pytest.raises(ModelRetry, match="without a verified"):
            validate_final_answer(ctx, "I've updated the application.")

    def test_unconfigured_documentation_search_is_a_truthful_limitation(self):
        ctx = MagicMock()
        ctx.deps.tool_catalog = "- database: list_tables"
        answer = (
            "The documentation search tool isn't available in this session because "
            "documentation search is not configured."
        )

        assert validate_final_answer(ctx, answer) == answer

        ctx.deps.tool_catalog = "- explain: search_user_docs"
        with pytest.raises(ModelRetry, match="current mode"):
            validate_final_answer(ctx, answer)

    def test_reused_or_empty_error_results_do_not_ground_success(self):
        ctx = MagicMock()
        ctx.messages = [
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="create_builders",
                        args={"builders": [{"name": "Restaurant", "type": "database"}]},
                        tool_call_id="reuse-builder",
                    )
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="create_builders",
                        content={
                            "created_builders": [],
                            "reused_builders": [
                                {
                                    "id": 41,
                                    "name": "Restaurant",
                                    "type": "database",
                                }
                            ],
                        },
                        tool_call_id="reuse-builder",
                    )
                ]
            ),
        ]
        with pytest.raises(ModelRetry, match="without a verified"):
            validate_final_answer(
                ctx, "The Restaurant database has been created successfully."
            )

        ctx.messages = [
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="update_fields",
                        args={"fields": [{"field_id": 9, "name": "Status"}]},
                        tool_call_id="failed-update",
                    )
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="update_fields",
                        content={
                            "updated_fields": [],
                            "errors": ["Field 9 is not accessible"],
                        },
                        tool_call_id="failed-update",
                    )
                ]
            ),
        ]
        with pytest.raises(ModelRetry, match="without a verified"):
            validate_final_answer(ctx, "I've updated the Status field successfully.")

    def test_partial_language_is_scoped_to_its_clause(self):
        ctx = MagicMock()
        ctx.messages = _mutation_messages(
            "create_workflows",
            {"workflows": [{"name": "Process Orders"}]},
            {
                "created_workflows": [{"id": 1, "name": "Process Orders"}],
                "errors": ["The action could not be configured"],
            },
            "partial-workflow",
        )

        with pytest.raises(ModelRetry, match="without a verified"):
            validate_final_answer(
                ctx, "I created the Process Orders workflow without errors."
            )

        partial = "I created the Process Orders workflow with errors."
        assert validate_final_answer(ctx, partial) == partial

    def test_table_notes_mark_the_result_as_partial(self):
        ctx = MagicMock()
        ctx.messages = _mutation_messages(
            "create_tables",
            {"database_id": 1, "tables": [{"name": "Orders"}]},
            {
                "created_tables": [{"id": 2, "name": "Orders"}],
                "notes": ["The Status field could not be created"],
            },
            "partial-table",
        )

        with pytest.raises(ModelRetry, match="without a verified"):
            validate_final_answer(ctx, "I created the Orders table successfully.")

        partial = "I created the Orders table with an error."
        assert validate_final_answer(ctx, partial) == partial

    def test_nested_empty_result_does_not_ground_success(self):
        ctx = MagicMock()
        ctx.messages = _mutation_messages(
            "create_view_filters",
            {"view_filters": [{"view_id": 1, "filters": []}]},
            {"created_view_filters": [{"view_id": 1, "filters": []}]},
            "empty-filters",
        )

        with pytest.raises(ModelRetry, match="without a verified"):
            validate_final_answer(ctx, "I created the filter.")

    def test_bare_handoff_without_completed_work_is_retried(self):
        ctx = MagicMock()
        ctx.messages = []
        handoff = (
            "I'm ready to set up the automation; let me know if you'd like me "
            "to create it now."
        )

        with pytest.raises(ModelRetry, match="hand an executable action"):
            validate_final_answer(ctx, handoff)

    def test_relaying_a_pending_ask_user_question_is_not_a_handoff(self):
        """After ask_user, the question reaches the user only through the
        final answer — retrying it with "Execute it now" would push the model
        to invent the data <intent> forbids inventing."""

        ctx = MagicMock()
        ctx.messages = []
        ctx.deps.pending_question = "Which table holds your customers?"
        relay = (
            "I couldn't find a Customers table — would you like me to create "
            "it, or should I use another table?"
        )

        assert validate_final_answer(ctx, relay) == relay

    @pytest.mark.parametrize(
        "answer",
        [
            "I've created the Projects table. Would you like me to add sample rows?",
            "Done. Let me know if you'd like me to create a matching view.",
            "I created the Projects table. Let me know if you'd like help with "
            "anything else.",
        ],
    )
    def test_optional_offer_after_completed_work_passes(self, answer):
        ctx = MagicMock()
        ctx.messages = _mutation_messages(
            "create_tables",
            {"database_id": 1, "tables": [{"name": "Projects"}]},
            {"created_tables": [{"id": 2, "name": "Projects"}]},
            "projects-table",
        )

        assert validate_final_answer(ctx, answer) == answer

    def test_destructive_confirmation_is_never_forced(self):
        ctx = MagicMock()
        ctx.messages = []
        confirmation = "Would you like me to delete the old field? It cannot be undone."

        assert validate_final_answer(ctx, confirmation) == confirmation
