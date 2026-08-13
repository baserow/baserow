"""
Regression net for pydantic-ai upgrades.

Each test here pins something the assistant module depends on that no other
test in the suite verifies: the import surface itself, a proxy attribute
that could be silently shadowed by a base-class change, and a span
attribute name that a mocked-attribute test can't detect a rename of.
"""

from datetime import datetime, timezone
from typing import Any

import pytest
from pydantic_ai import Agent, InstrumentationSettings, ModelRetry, RunContext, Tool
from pydantic_ai._thinking_part import split_content_into_text_and_thinking
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.exceptions import ModelRetry as ModelRetryFromExceptions
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models import (
    KnownModelName,
    Model,
    ModelRequestParameters,
    ModelResponseStreamEvent,
    StreamedResponse,
    infer_model,
)
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.run import AgentRunResultEvent
from pydantic_ai.settings import ModelSettings
from pydantic_ai.toolsets import AbstractToolset, CombinedToolset, FunctionToolset
from pydantic_ai.toolsets.abstract import AgentDepsT, ToolsetTool
from pydantic_ai.usage import RequestUsage, UsageLimits

from baserow_enterprise.assistant.assistant import _strip_think_tags
from baserow_enterprise.assistant.retrying_model import _ErrorRecoveringStream
from baserow_enterprise.assistant.tools.database.agents import (
    formula_generation_agent,
)

# ---------------------------------------------------------------------------
# Step 1: the symbol surface
# ---------------------------------------------------------------------------


def test_pydantic_ai_symbol_surface_the_assistant_depends_on():
    """Pins every pydantic-ai symbol enterprise/backend/src/baserow_enterprise/assistant imports.

    A rename or removal breaks this test with an ImportError before it can
    surface as a mid-run failure in production. Public symbols are pinned
    alongside private ones, because both move.
    """

    assert Agent is not None
    assert InstrumentationSettings is not None
    assert ModelRetry is not None
    assert RunContext is not None
    assert Tool is not None

    assert ModelHTTPError is not None
    assert ModelRetryFromExceptions is ModelRetry

    assert FunctionToolCallEvent is not None
    assert FunctionToolResultEvent is not None
    assert ModelMessage is not None
    assert ModelMessagesTypeAdapter is not None
    assert ModelRequest is not None
    assert ModelResponse is not None
    assert PartDeltaEvent is not None
    assert PartStartEvent is not None
    assert TextPart is not None
    assert TextPartDelta is not None
    assert ThinkingPart is not None
    assert ThinkingPartDelta is not None
    assert ToolCallPart is not None
    assert UserPromptPart is not None

    assert KnownModelName is not None
    assert Model is not None
    assert ModelRequestParameters is not None
    assert ModelResponseStreamEvent is not None
    assert StreamedResponse is not None
    assert infer_model is not None

    assert AnthropicModel is not None
    assert GoogleModel is not None
    assert GroqModel is not None
    assert OpenAIChatModel is not None
    assert WrapperModel is not None

    assert AnthropicProvider is not None
    assert GoogleProvider is not None
    assert GroqProvider is not None
    assert OllamaProvider is not None
    assert OpenAIProvider is not None

    assert AgentRunResultEvent is not None
    assert ModelSettings is not None

    assert AbstractToolset is not None
    assert CombinedToolset is not None
    assert FunctionToolset is not None
    assert AgentDepsT is not None
    assert ToolsetTool is not None

    assert UsageLimits is not None

    # Private module, no public equivalent (assistant.py:9) — unguaranteed across releases.
    assert split_content_into_text_and_thinking is not None
    assert _strip_think_tags("a<think>b</think>c") == "ac"


# ---------------------------------------------------------------------------
# Step 2: the usage-delegation contract
# ---------------------------------------------------------------------------


def _make_fake_streamed_response(
    *,
    input_tokens: int,
    output_tokens: int,
    state: str = "complete",
    metadata: dict[str, Any] | None = None,
) -> StreamedResponse:
    """Build a real StreamedResponse subclass with distinguishable, non-zero usage."""

    class _FakeStreamedResponse(StreamedResponse):
        def __init__(self) -> None:
            super().__init__(model_request_parameters=ModelRequestParameters())
            self._usage = RequestUsage(
                input_tokens=input_tokens, output_tokens=output_tokens
            )
            self.state = state
            self.metadata = metadata
            self.close_stream_called = False

        @property
        def model_name(self) -> str:
            return "test-model"

        @property
        def provider_name(self) -> str | None:
            return "test"

        @property
        def provider_url(self) -> str | None:
            return "http://test"

        @property
        def timestamp(self) -> datetime:
            return datetime(2026, 8, 12, tzinfo=timezone.utc)

        async def _get_event_iterator(self):
            return
            yield  # pragma: no cover — never iterated in this test

        async def close_stream(self) -> None:
            self.close_stream_called = True

    return _FakeStreamedResponse()


def test_error_recovering_stream_reports_the_inner_usage():
    """Guards the proxy against StreamedResponse class attributes shadowing __getattr__."""

    inner = _make_fake_streamed_response(input_tokens=11, output_tokens=22)
    proxy = _ErrorRecoveringStream(inner)

    assert proxy.usage.input_tokens == 11
    assert proxy.usage.output_tokens == 22


def test_error_recovering_stream_reports_the_inner_state_and_metadata():
    """Without a delegating property the proxy reads its own class-level
    defaults instead of the inner stream's, hiding a suspended (e.g. Anthropic
    pause_turn) segment behind a 'complete' status and dropping its metadata."""

    inner = _make_fake_streamed_response(
        input_tokens=1, output_tokens=1, state="suspended", metadata={"pin": "value"}
    )
    proxy = _ErrorRecoveringStream(inner)

    assert proxy.state == "suspended"
    assert proxy.metadata == {"pin": "value"}


@pytest.mark.asyncio
async def test_error_recovering_stream_delegates_close_stream():
    """close_stream() must reach the inner stream's connection teardown rather
    than raising the base class's NotImplementedError."""

    inner = _make_fake_streamed_response(input_tokens=1, output_tokens=1)
    proxy = _ErrorRecoveringStream(inner)

    await proxy.close_stream()

    assert inner.close_stream_called is True


# ---------------------------------------------------------------------------
# Step 3: the telemetry attribute contract
# ---------------------------------------------------------------------------


def test_generation_span_carries_the_usage_attributes_telemetry_reads():
    """Runs a real agent under an in-memory exporter and reads attrs pydantic-ai
    actually emitted, unlike test_telemetry.py's test_generation_span which sets
    the attributes it then asserts on."""

    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )
    from pydantic_ai.models.test import TestModel

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    Agent.instrument_all(InstrumentationSettings(tracer_provider=provider))
    try:
        agent = Agent(output_type=str, name="usage_contract_agent")
        agent.run_sync("hello", model=TestModel(call_tools=[]))
    finally:
        Agent.instrument_all(False)

    chat_spans = [
        s for s in exporter.get_finished_spans() if s.name.startswith("chat ")
    ]
    assert chat_spans, "pydantic-ai emitted no chat span"

    attrs = dict(chat_spans[0].attributes)
    usage_keys = sorted(k for k in attrs if "usage" in k)
    assert "gen_ai.usage.input_tokens" in attrs, (
        f"telemetry.py reads gen_ai.usage.*; span has {usage_keys}"
    )
    assert "gen_ai.usage.output_tokens" in attrs, (
        f"telemetry.py reads gen_ai.usage.*; span has {usage_keys}"
    )


# ---------------------------------------------------------------------------
# Step 4: the end_strategy contract
# ---------------------------------------------------------------------------


def test_formula_generation_agent_skips_tool_calls_once_output_succeeds():
    """The default changed from 'early' to 'graceful' in v2 (see EndStrategy
    docstring). formula_generation_agent pins 'early' so a tool call emitted
    alongside a successful structured output is skipped, matching v1 — a
    mocked-run_sync test can't detect a dropped end_strategy kwarg."""

    tool_calls = []

    def track_tool(x: str) -> str:
        tool_calls.append(x)
        return "tracked"

    def func(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if len(messages) == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="track_tool", args={"x": "a"}, tool_call_id="1"
                    ),
                    ToolCallPart(
                        tool_name="final_result",
                        args={
                            "table_id": 1,
                            "field_name": "f",
                            "formula": "'ok'",
                            "formula_type": "text",
                            "is_formula_valid": True,
                        },
                        tool_call_id="2",
                    ),
                ]
            )
        return ModelResponse(parts=[TextPart(content="done")])

    toolset = FunctionToolset([Tool(track_tool)])
    result = formula_generation_agent.run_sync(
        "generate a formula",
        model=FunctionModel(func),
        toolsets=[toolset],
    )

    assert result.output.formula == "'ok'"
    assert tool_calls == []


# ---------------------------------------------------------------------------
# Step 5: the sub-agent provider-prefix contract
# ---------------------------------------------------------------------------


def test_google_provider_names_pydantic_ai_accepts():
    """Sub-agents (tools/database/agents.py, tools/shared/agents.py,
    tools/toolset.py) pass their model string straight to pydantic-ai's own
    infer_model, bypassing Baserow's _resolve_model, so the names
    get_model_string() emits must exist in the real provider registry."""

    from pydantic_ai.providers import infer_provider_class

    assert infer_provider_class("google") is not None
    assert infer_provider_class("google-cloud") is not None

    with pytest.raises(ValueError, match="Unknown provider"):
        infer_provider_class("google-gla")
    with pytest.raises(ValueError, match="Unknown provider"):
        infer_provider_class("google-vertex")
