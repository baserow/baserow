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
from baserow_enterprise.assistant.model_profiles import _DEFAULT_PROFILE
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

    def get_formula_type(table_id: int, field_name: str, formula: str) -> str:
        return "text"

    def func(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        # The output validator only accepts formulas get_formula_type validated.
        if len(messages) == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="get_formula_type",
                        args={"table_id": 1, "field_name": "f", "formula": "'ok'"},
                        tool_call_id="0",
                    ),
                ]
            )
        if len(messages) == 3:
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

    toolset = FunctionToolset([Tool(track_tool), Tool(get_formula_type)])
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


# ---------------------------------------------------------------------------
# Step 6: the gpt-5.6 reasoning contract
# ---------------------------------------------------------------------------


def test_gpt_5_6_still_reasons_by_default_and_can_be_turned_off():
    """_REASONING_OFF_PROFILE only exists because gpt-5.6 reasons by default,
    which makes OpenAI reject function tools on /v1/chat/completions. If a
    pydantic-ai upgrade flips either fact the workaround is wrong, not stale."""

    from pydantic_ai.profiles.openai import openai_model_profile

    profile = openai_model_profile("gpt-5.6-luna")

    assert profile.get("openai_reasoning_enabled_by_default") is True
    assert profile.get("openai_supports_reasoning_effort_none") is True


def test_reasoning_effort_none_keeps_the_sampling_params_we_set():
    """Turning reasoning off is what lets our temperature survive: pydantic-ai
    silently drops every sampling param while reasoning is active."""

    from pydantic_ai.models.openai import (
        _drop_sampling_params_for_reasoning,  # noqa: PLC2701
    )
    from pydantic_ai.profiles.openai import openai_model_profile

    profile = openai_model_profile("gpt-5.6-luna")
    params = ModelRequestParameters()

    with_reasoning_off = {"temperature": 0.3, "openai_reasoning_effort": "none"}
    _drop_sampling_params_for_reasoning(profile, with_reasoning_off, params)
    assert with_reasoning_off["temperature"] == 0.3

    with_default_reasoning = {"temperature": 0.3}
    with pytest.warns(UserWarning, match="Sampling parameters"):
        _drop_sampling_params_for_reasoning(profile, with_default_reasoning, params)
    assert "temperature" not in with_default_reasoning


@pytest.mark.parametrize(
    "model",
    ["openai:gpt-5.6-luna", "openai:gpt-5.6-sol", "openai:gpt-5.6-terra"],
)
def test_gpt_5_6_runs_with_reasoning_off_in_every_role(model):
    from baserow_enterprise.assistant.model_profiles import (
        ORCHESTRATOR,
        SAMPLE,
        SUBAGENT,
        SUGGESTIONS,
        TITLE,
        UTILITY,
        get_model_settings,
    )

    for role in (ORCHESTRATOR, SUBAGENT, UTILITY, SAMPLE, TITLE, SUGGESTIONS):
        settings = get_model_settings(model, role)
        assert settings["openai_reasoning_effort"] == "none", role
        assert settings["temperature"] == _DEFAULT_PROFILE[role]["temperature"], role


def test_other_models_are_left_alone_by_the_gpt_5_6_workaround():
    from baserow_enterprise.assistant.model_profiles import (
        ORCHESTRATOR,
        get_model_settings,
    )

    for model in ("groq:openai/gpt-oss-120b", "openai:gpt-5-mini"):
        assert "openai_reasoning_effort" not in get_model_settings(model, ORCHESTRATOR)


def test_every_sub_agent_run_passes_its_model_profile():
    """A sub-agent invoked without model_settings silently ignores
    _MODEL_PROFILES, which is how gpt-5.6 kept sending reasoning_effort with
    function tools and 400ing. Grep is the only way to catch a missing kwarg
    at a call site no test exercises."""

    import re
    from pathlib import Path

    assistant = (
        Path(__file__).resolve().parents[3] / "src" / "baserow_enterprise" / "assistant"
    )
    assert assistant.is_dir(), f"cannot find the assistant package at {assistant}"
    # harness/judge pass a bare model string and let pydantic-ai resolve it;
    # check_lm_ready_or_raise is a tool-less "respond ok" connectivity probe.
    exempt = {"evals/harness.py", "evals/judge.py", "model_profiles.py"}

    offenders = []
    scanned = 0
    for path in assistant.rglob("*.py"):
        scanned += 1
        rel = path.relative_to(assistant).as_posix()
        if rel in exempt:
            continue
        source = path.read_text()
        for match in re.finditer(r"\b(\w*agent)\.run(?:_sync)?\(", source):
            if source[match.start() - 1] == "`":
                continue
            call = source[match.start() : match.start() + 400]
            if "model_settings" not in call:
                line = source[: match.start()].count("\n") + 1
                offenders.append(f"{rel}:{line} {match.group(1)}")

    assert scanned > 50, f"only scanned {scanned} files; the glob is wrong"
    assert not offenders, (
        "these agent calls skip get_model_settings(), so per-model profiles "
        f"never reach them: {offenders}"
    )
