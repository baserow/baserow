"""
Posthog telemetry integration for the Baserow Assistant.

Hooks into pydantic-ai's OpenTelemetry instrumentation to capture LLM
generation and tool call events, mapping them to PostHog's AI analytics
event schema (``$ai_trace``, ``$ai_generation``, ``$ai_span``).

Architecture:

    PosthogTracingCallback  -- per-request context manager that emits the
                              top-level ``$ai_trace`` event and publishes
                              trace metadata via a ``ContextVar`` for the
                              span exporter.

    PosthogSpanExporter     -- OpenTelemetry ``SpanExporter`` that maps
                              pydantic-ai spans to PostHog events:
                                ``chat ...``       -> ``$ai_generation``
                                ``running tool``   -> ``$ai_span``
                              ``agent run`` / ``running tools`` are skipped.

    setup_instrumentation() -- one-time wiring of the span processor into a
                              ``TracerProvider`` + ``Agent.instrument_all()``.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence
from uuid import uuid4

from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import SpanKind

from baserow.core.posthog import get_posthog_client
from baserow_enterprise.assistant.models import AssistantChat

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _uuid() -> str:
    return str(uuid4())


def _posthog_capture(distinct_id: str, event: str, properties: dict, **kwargs):
    """Send a single event to PostHog with standardised error handling."""

    posthog_client = get_posthog_client()
    try:
        posthog_client.capture(
            distinct_id=distinct_id, event=event, properties=properties, **kwargs
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Trace context (ContextVars shared between callback and span exporter)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _TraceContext:
    """Immutable snapshot of per-request trace metadata."""

    trace_id: str
    user_id: str
    workspace_id: str
    chat_uuid: str


_trace_ctx: ContextVar[_TraceContext | None] = ContextVar("_trace_ctx", default=None)

# Tool names collected during a trace for the $ai_trace summary.
_tool_calls: ContextVar[list[str]] = ContextVar("_tool_calls")


# ---------------------------------------------------------------------------
# Message format conversion (pydantic-ai -> PostHog)
# ---------------------------------------------------------------------------

# pydantic-ai key names  ->  PostHog key names
_PART_TRANSFORMS = {
    "text": lambda p: {
        "type": "text",
        "text": p.get("content", ""),
    },
    "tool_call": lambda p: {
        "type": "tool_call",
        "tool_call_id": p.get("id", ""),
        "name": p.get("name", ""),
        "arguments": p.get("args", {}),
    },
    "tool_return": lambda p: {
        "type": "tool_result",
        "tool_call_id": p.get("tool_call_id", ""),
        "content": p.get("content", ""),
    },
    "thinking": lambda p: {
        "type": "thinking",
        "text": p.get("content", ""),
    },
}


def _safe_json_attr(attrs: dict, key: str) -> list | dict | None:
    """Extract a JSON-serialised span attribute, returning None if missing or
    unparseable."""

    val = attrs.get(key)
    if val is None:
        return None
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return None
    return val


def _pydantic_messages_to_posthog(messages: list[dict]) -> list[dict]:
    """Convert pydantic-ai message dicts to PostHog's expected format.

    pydantic-ai: ``{"role": ..., "parts": [{"type": "text", "content": ...}]}``
    PostHog:     ``{"role": ..., "content": [{"type": "text", "text": ...}]}``
    """

    result = []
    for msg in messages:
        content_parts = []
        for part in msg.get("parts", []):
            ptype = part.get("type", "text")
            transform = _PART_TRANSFORMS.get(ptype)
            content_parts.append(transform(part) if transform else part)
        result.append({"role": msg.get("role", "unknown"), "content": content_parts})
    return result


# ---------------------------------------------------------------------------
# Span helpers (shared by _emit_generation and _emit_tool_span)
# ---------------------------------------------------------------------------


def _span_latency(span: ReadableSpan) -> float | None:
    """Compute span duration in seconds from OTel nanosecond timestamps."""

    if span.start_time and span.end_time:
        return (span.end_time - span.start_time) / 1e9
    return None


def _span_id_properties(span: ReadableSpan) -> dict:
    """Return ``$ai_span_id`` (and ``$ai_parent_id`` if present)."""

    props: dict = {"$ai_span_id": f"{span.context.span_id:016x}"}
    if span.parent:
        props["$ai_parent_id"] = f"{span.parent.span_id:016x}"
    return props


def _base_properties(ctx: _TraceContext) -> dict:
    """Properties common to every PostHog event within a trace."""

    return {
        "$ai_trace_id": ctx.trace_id,
        "$ai_session_id": ctx.chat_uuid,
        "workspace_id": ctx.workspace_id,
    }


def _extract_reasoning(output_messages: list[dict]) -> str | None:
    """Join all ``thinking`` parts from output messages into a single string."""

    parts = [
        content
        for msg in output_messages
        for part in msg.get("parts", [])
        if part.get("type") == "thinking" and (content := part.get("content"))
    ]
    return "\n".join(parts) if parts else None


# ---------------------------------------------------------------------------
# PosthogSpanExporter
# ---------------------------------------------------------------------------

# Model setting keys emitted by pydantic-ai as ``gen_ai.request.*`` attrs.
_MODEL_PARAM_KEYS = (
    "temperature",
    "max_tokens",
    "top_p",
    "seed",
    "presence_penalty",
    "frequency_penalty",
)


class PosthogSpanExporter(SpanExporter):
    """Maps pydantic-ai OTel spans to PostHog LLM analytics events.

    ``chat {model}``   -> ``$ai_generation``
    ``running tool``   -> ``$ai_span``
    ``agent run`` / ``running tools`` -> skipped
    """

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        ctx = _trace_ctx.get()
        if ctx is None:
            return SpanExportResult.SUCCESS

        for span in spans:
            try:
                self._process_span(span, ctx)
            except Exception:
                pass

        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis: int = 0) -> bool:
        return True

    # -- internal ----------------------------------------------------------

    def _process_span(self, span: ReadableSpan, ctx: _TraceContext):
        attrs = dict(span.attributes or {})

        if span.kind == SpanKind.CLIENT and span.name.startswith("chat "):
            self._emit_generation(span, attrs, ctx)
        elif span.name == "running tool":
            self._emit_tool_span(span, attrs, ctx)

    def _emit_generation(self, span: ReadableSpan, attrs: dict, ctx: _TraceContext):
        """Map a ``chat {model}`` span to ``$ai_generation``."""

        input_messages = _safe_json_attr(attrs, "gen_ai.input.messages")
        output_messages = _safe_json_attr(attrs, "gen_ai.output.messages")

        properties = {
            **_base_properties(ctx),
            "$ai_model": (
                attrs.get("gen_ai.response.model") or attrs.get("gen_ai.request.model")
            ),
            "$ai_provider": (
                attrs.get("gen_ai.provider.name") or attrs.get("gen_ai.system")
            ),
            "$ai_input_tokens": attrs.get("gen_ai.usage.input_tokens"),
            "$ai_output_tokens": attrs.get("gen_ai.usage.output_tokens"),
        }

        # Model parameters
        model_params = {
            key: val
            for key in _MODEL_PARAM_KEYS
            if (val := attrs.get(f"gen_ai.request.{key}")) is not None
        }
        if model_params:
            properties["$ai_model_parameters"] = model_params

        # System prompt
        system_instructions = _safe_json_attr(attrs, "gen_ai.system_instructions")
        if system_instructions and isinstance(system_instructions, list):
            system_text = "\n".join(
                p.get("content", "") for p in system_instructions if isinstance(p, dict)
            )
            if system_text:
                properties["$ai_system_prompt"] = system_text

        # Input / output messages
        if input_messages:
            properties["$ai_input"] = _pydantic_messages_to_posthog(input_messages)
        if output_messages:
            properties["$ai_output_choices"] = _pydantic_messages_to_posthog(
                output_messages
            )

        latency = _span_latency(span)
        if latency is not None:
            properties["$ai_latency"] = latency

        # Tool definitions and names
        tool_definitions = _safe_json_attr(attrs, "gen_ai.tool.definitions")
        if tool_definitions and isinstance(tool_definitions, list):
            tool_names = [
                t.get("name", "?") for t in tool_definitions if isinstance(t, dict)
            ]
            if tool_names:
                properties["$ai_tools"] = tool_names
            properties["$ai_tool_definitions"] = tool_definitions

        # Reasoning / thinking
        if output_messages and isinstance(output_messages, list):
            reasoning = _extract_reasoning(output_messages)
            if reasoning:
                properties["$ai_reasoning"] = reasoning

        properties.update(_span_id_properties(span))
        _posthog_capture(ctx.user_id, "$ai_generation", properties)

    def _emit_tool_span(self, span: ReadableSpan, attrs: dict, ctx: _TraceContext):
        """Map a ``running tool`` span to ``$ai_span``."""

        tool_name = attrs.get("gen_ai.tool.name", "unknown_tool")

        # Record for the trace summary.
        try:
            _tool_calls.get().append(tool_name)
        except LookupError:
            pass

        tool_args = _safe_json_attr(attrs, "tool_arguments")

        properties = {
            **_base_properties(ctx),
            "$ai_span_name": f"Tool: {tool_name}",
            "$ai_input_state": tool_args or {},
            "$ai_output_state": attrs.get("tool_response"),
        }

        # Chain-of-thought reasoning from the "thought" argument
        if isinstance(tool_args, dict) and tool_args.get("thought"):
            properties["$ai_reasoning"] = tool_args["thought"]

        latency = _span_latency(span)
        if latency is not None:
            properties["$ai_latency"] = latency

        properties.update(_span_id_properties(span))
        _posthog_capture(ctx.user_id, "$ai_span", properties)


# ---------------------------------------------------------------------------
# One-time instrumentation setup
# ---------------------------------------------------------------------------

_instrumentation_ready = False


def setup_instrumentation():
    """Activate pydantic-ai's OTel instrumentation with PostHog export.

    Safe to call multiple times (subsequent calls are no-ops).
    Does nothing when PostHog is disabled.
    """

    global _instrumentation_ready
    if _instrumentation_ready:
        return

    from django.conf import settings as django_settings

    posthog_enabled = getattr(django_settings, "POSTHOG_ENABLED", False)
    if not posthog_enabled:
        return

    # SimpleSpanProcessor exports synchronously in the same context where
    # _trace_ctx is set, avoiding background-thread ContextVar issues.
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from pydantic_ai import Agent, InstrumentationSettings

    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(PosthogSpanExporter()))

    Agent.instrument_all(
        InstrumentationSettings(
            tracer_provider=tracer_provider,
            include_content=True,
        )
    )

    _instrumentation_ready = True


# ---------------------------------------------------------------------------
# PosthogTracingCallback — per-request trace lifecycle
# ---------------------------------------------------------------------------


class PosthogTracingCallback:
    """Per-request trace lifecycle. Creates the ``$ai_trace`` event and
    publishes ``_TraceContext`` for the span exporter."""

    def __init__(self):
        self.chat: AssistantChat | None = None
        self.human_msg: str | None = None
        self.trace_id: str | None = None
        self.span_id: str | None = None
        self.user_id: str | None = None
        self.workspace_id: str | None = None
        self.chat_uuid: str | None = None
        self.trace_outputs = None

    @contextmanager
    def trace(self, chat: AssistantChat, human_message: str):
        """Context manager that scopes a single assistant execution.

        Publishes ``_trace_ctx`` so ``PosthogSpanExporter`` can attach trace
        metadata to child ``$ai_generation`` / ``$ai_span`` events.
        """

        self.chat = chat
        self.human_msg = human_message
        self.trace_id = _uuid()
        self.span_id = _uuid()
        self.user_id = str(chat.user_id)
        self.workspace_id = str(chat.workspace_id)
        self.chat_uuid = str(chat.uuid)
        self.trace_outputs = None

        start_time = _utc_now()

        token = _trace_ctx.set(
            _TraceContext(
                trace_id=self.trace_id,
                user_id=self.user_id,
                workspace_id=self.workspace_id,
                chat_uuid=self.chat_uuid,
            )
        )
        tools_token = _tool_calls.set([])

        exception = None
        try:
            yield self
        except Exception as exc:
            exception = exc
            raise
        finally:
            tool_call_names = _tool_calls.get([])
            _trace_ctx.reset(token)
            _tool_calls.reset(tools_token)

            output_state = self.trace_outputs if exception is None else str(exception)
            if tool_call_names:
                if output_state is None:
                    output_state = {}
                if isinstance(output_state, dict):
                    output_state["tool_calls"] = tool_call_names

            self._capture_event(
                "$ai_trace",
                timestamp=start_time,
                properties={
                    "$ai_session_id": chat.uuid,
                    "$ai_span_name": f"{self.user_id}: {human_message[:20]}",
                    "$ai_span_id": self.span_id,
                    "$ai_latency": (_utc_now() - start_time).total_seconds(),
                    "$ai_is_error": exception is not None,
                    "$ai_input_state": {"user_message": human_message},
                    "$ai_output_state": output_state,
                },
            )

            try:
                get_posthog_client().flush()
            except Exception:
                pass

    def set_trace_output(self, output: str):
        """Record the agent's final answer for the ``$ai_trace`` event."""

        self.trace_outputs = {"answer": output}

    def _capture_event(self, event: str, **kwargs):
        """Capture a PostHog event, merging in default trace properties."""

        kwargs["properties"] = {
            **kwargs.get("properties", {}),
            "$ai_trace_id": self.trace_id,
            "$ai_session_id": self.chat_uuid,
            "workspace_id": self.workspace_id,
        }
        _posthog_capture(str(self.user_id), event, **kwargs)
