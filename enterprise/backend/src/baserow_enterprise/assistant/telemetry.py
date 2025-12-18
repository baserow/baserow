"""
Posthog telemetry integration for the Baserow Assistant.

This module provides tracing callbacks that capture DSPy execution flows
and send structured events to Posthog for LLM analytics.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import udspy
from udspy.callback import BaseCallback

from baserow.core.posthog import get_posthog_client
from baserow_enterprise.assistant.models import AssistantChat


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _uuid() -> str:
    return str(uuid4())


class PosthogTracingCallback(BaseCallback):
    """
    Captures uDSPy execution traces and sends events to Posthog.

    This callback tracks:
    - uDSPy module execution (ChainOfThought, ReAct, Predict)
    - LLM API calls (OpenAI, Groq, etc.)
    - Tool invocations
    - Performance metrics and token usage

    Each instance is created per Assistant call with trace context, so
    multiple concurrent traces can be captured independently.
    """

    def __init__(self):
        super().__init__()

        self.chat: AssistantChat | None = None
        self.human_msg: str | None = None
        self.trace_id: str | None = None
        self.span_id: str | None = None
        self.user_id: str | None = None
        self.workspace_id: str | None = None
        self.chat_uuid: str | None = None
        self.spans: dict[str, dict] = {}
        self.span_ids: list[str] = []

    @contextmanager
    def trace(self, chat: AssistantChat, human_message: str):
        """
        Context manager for tracing an assistant execution.
        Initializes trace context and captures the overall trace event.
        It also patches the OpenAI client to auto-capture generation events.

        :param chat: The AssistantChat instance
        :param human_message: The initial user message
        """

        from posthog.ai.openai import AsyncOpenAI

        self.chat = chat
        self.human_msg = human_message

        self.trace_id = _uuid()
        self.span_id = _uuid()
        self.user_id = str(chat.user_id)
        self.workspace_id = str(chat.workspace_id)
        self.chat_uuid = str(chat.uuid)

        start_time = _utc_now()
        self.spans = {}
        self.span_ids = [self.span_id]
        self.trace_outputs = None

        # patch the OpenAI client to automatically send the generation event
        lm = udspy.settings._context_lm.get()
        openai_client = lm.client

        # Check if client is already a PostHog-wrapped client by checking its
        # module. We avoid isinstance() here because it can fail when the class
        # is mocked in tests.
        is_posthog_client = "posthog" in type(openai_client).__module__
        if not is_posthog_client:
            lm.client = AsyncOpenAI(
                api_key=openai_client.api_key,
                base_url=openai_client.base_url,
                posthog_client=get_posthog_client(),
            )

        exception = None
        try:
            yield self
        except Exception as exc:
            exception = exc
            raise
        finally:
            # Stop trace
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
                    "$ai_output_state": self.trace_outputs
                    if exception is None
                    else str(exception),
                },
            )

    def _capture_event(self, event: str, **kwargs):
        """
        Capture a Posthog event if Posthog is enabled.

        :param event: Event name (e.g., "$ai_generation")
        :param properties: Event properties dictionary
        """

        default_props = {
            "$ai_trace_id": self.trace_id,
            "$ai_session_id": self.chat_uuid,
            "workspace_id": self.workspace_id,
        }
        if "properties" in kwargs:
            kwargs["properties"].update(default_props)
        else:
            kwargs["properties"] = default_props

        posthog_client = get_posthog_client()
        posthog_client.capture(
            distinct_id=str(self.user_id),
            event=event,
            **kwargs,
        )  # noqa: W505

    def on_module_start(self, call_id: str, instance: Any, inputs: dict):
        """
        Track the start of a DSPy module execution.

        Captures ChainOfThought, ReAct, Predict, and other module types.

        :param call_id: Unique identifier for this call
        :param instance: The DSPy module instance
        :param inputs: Input dictionary passed to the module
        """

        module_type = instance.__class__.__name__
        parent_span_id = self.span_ids[-1] if self.span_ids else None
        span_id = call_id
        self.span_ids.append(span_id)
        span = {
            "start_time": _utc_now(),
            "properties": {
                "$ai_span_name": module_type,
                "$ai_span_id": span_id,
                "$ai_parent_span_id": parent_span_id,
            },
        }
        self.spans[span_id] = span

        def _update_span_with_signature_data(signature):
            adapter = udspy.ChatAdapter()
            input_fields = ", ".join(signature.get_input_fields().keys())
            output_fields = ", ".join(signature.get_output_fields())
            span["properties"]["$ai_input_state"] = {
                "signature": f"{input_fields} -> {output_fields}",
                "instructions": adapter.format_instructions(signature),
                **inputs["kwargs"],
            }

        if isinstance(instance, (udspy.Predict, udspy.ReAct)):
            _update_span_with_signature_data(instance.signature)
        elif isinstance(instance, udspy.ChainOfThought):
            _update_span_with_signature_data(instance.original_signature)

    def on_module_end(self, call_id: str, outputs: Any, exception: Exception | None):
        """
        Remove the span from the stack together with all the started $ai_generation
        spans appended in `on_lm_start`

        Args:
            call_id: Unique identifier for this call
            outputs: Module output (if successful)
            exception: Exception raised (if failed)
        """

        while (span_id := self.span_ids.pop()) != call_id:
            continue

        span = self.spans.pop(span_id)
        start_time = span.pop("start_time")
        span["properties"].update(
            {
                "$ai_latency": (_utc_now() - start_time).total_seconds(),
                "$ai_is_error": exception is not None,
                "$ai_output_state": outputs if exception is None else str(exception),
            }
        )

        if isinstance(outputs, dict) and "answer" in outputs:
            self.trace_outputs = {
                k: v
                for k, v in outputs.items()
                if k not in ["module", "native_tool_calls"]
            }

        self._capture_event("$ai_span", timestamp=start_time, **span)

    def on_lm_start(self, call_id: str, instance: Any, inputs: dict):
        """
        Only enrich posthog properties that will be sent automatically
        by the patched openai client.
        Add the span_id to the stack so any tool call will be shown
        as a child span.

        Args:
            call_id: Unique identifier for this call
            instance: The LM instance
            inputs: API call parameters (model, messages, temperature, etc.)
        """

        parent_span_id = self.span_ids[-1] if self.span_ids else None
        kwargs = inputs["kwargs"]
        span_id = call_id
        self.span_ids.append(span_id)
        kwargs["posthog_distinct_id"] = self.user_id
        kwargs["posthog_trace_id"] = self.trace_id
        kwargs["posthog_properties"] = {
            "$ai_session_id": self.chat_uuid,
            "$ai_parent_span_id": parent_span_id,
            "$ai_span_id": span_id,
            "workspace_id": self.workspace_id,
            "$ai_provider": instance.provider,
        }

    def on_lm_end(self, call_id: str, outputs: Any, exception: Exception | None):
        """
        Automatically tracked by the patched openai client.

        :param call_id: Unique identifier for this call
        :param outputs: LLM response object
        :param exception: Exception raised (if failed)
        """

        pass

    def on_tool_start(self, call_id: str, instance: Any, inputs: dict):
        """
        Track the start of a tool invocation.

        Args:
            call_id: Unique identifier for this call
            instance: The tool instance
            inputs: Tool input parameters
        """

        tool_name = getattr(instance, "name", instance.__class__.__name__)

        span_id = call_id
        parent_span_id = self.span_ids[-1] if self.span_ids else None
        self.spans[span_id] = {
            "start_time": _utc_now(),
            "properties": {
                "$ai_span_name": f"Tool: {tool_name}",
                "$ai_span_id": span_id,
                "$ai_parent_span_id": parent_span_id,
                "$ai_input_state": inputs,
            },
        }

    def on_tool_end(self, call_id: str, outputs: Any, exception: Exception | None):
        """
        Track the completion of a tool invocation.

        Args:
            call_id: Unique identifier for this call
            outputs: Tool output
            exception: Exception raised (if failed)
        """

        span_id = call_id
        span = self.spans.pop(span_id)
        start_time = span.pop("start_time")
        span["properties"].update(
            {
                "$ai_latency": (_utc_now() - start_time).total_seconds(),
                "$ai_is_error": exception is not None,
                "$ai_output_state": outputs if exception is None else str(exception),
            }
        )
        self._capture_event("$ai_span", timestamp=start_time, **span)
