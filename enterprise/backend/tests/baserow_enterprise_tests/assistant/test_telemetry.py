import json
from unittest.mock import MagicMock, patch

import pytest

from baserow_enterprise.assistant.models import AssistantChat
from baserow_enterprise.assistant.telemetry import (
    PosthogSpanProcessor,
    PosthogTracingCallback,
    _pydantic_messages_to_posthog,
    _tool_calls,
    _trace_ctx,
    _TraceContext,
)


@pytest.fixture
def assistant_chat_fixture(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    return AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )


@pytest.mark.django_db
class TestPosthogTracingCallback:
    @patch("baserow_enterprise.assistant.telemetry.get_posthog_client")
    def test_trace_context_manager_success(
        self, mock_get_client, assistant_chat_fixture
    ):
        """Test the trace context manager in a successful execution flow."""

        mock_posthog = MagicMock()
        mock_get_client.return_value = mock_posthog

        callback = PosthogTracingCallback()

        with callback.trace(assistant_chat_fixture, "Hello"):
            assert callback.trace_id is not None
            assert callback.span_id is not None
            assert callback.user_id == str(assistant_chat_fixture.user_id)

        # Verify trace event captured
        mock_posthog.capture.assert_called_once()
        call_args = mock_posthog.capture.call_args

        # Check the event structure
        assert call_args.kwargs["distinct_id"] == str(assistant_chat_fixture.user_id)
        assert call_args.kwargs["event"] == "$ai_trace"
        assert "timestamp" in call_args.kwargs

        # Check properties
        props = call_args.kwargs["properties"]
        assert props["$ai_trace_id"] == callback.trace_id
        assert props["$ai_session_id"] == str(assistant_chat_fixture.uuid)
        assert props["workspace_id"] == str(assistant_chat_fixture.workspace_id)
        assert props["$ai_span_name"] == f"{assistant_chat_fixture.user_id}: Hello"
        assert props["$ai_span_id"] == callback.span_id
        assert props["$ai_latency"] >= 0
        assert props["$ai_is_error"] is False
        assert props["$ai_input_state"] == {"user_message": "Hello"}
        assert props["$ai_output_state"] is None

    @patch("baserow_enterprise.assistant.telemetry.get_posthog_client")
    def test_trace_context_manager_exception(
        self, mock_get_client, assistant_chat_fixture
    ):
        """Test the trace context manager when an exception occurs."""

        mock_posthog = MagicMock()
        mock_get_client.return_value = mock_posthog

        callback = PosthogTracingCallback()

        with pytest.raises(ValueError):
            with callback.trace(assistant_chat_fixture, "Hello"):
                raise ValueError("Test error")

        # Verify trace event captured with error
        call_args = mock_posthog.capture.call_args
        assert call_args is not None
        assert call_args.kwargs["event"] == "$ai_trace"
        assert call_args.kwargs["properties"]["$ai_is_error"] is True

    @patch("baserow_enterprise.assistant.telemetry.get_posthog_client")
    def test_trace_with_output(self, mock_get_client, assistant_chat_fixture):
        """Test that trace output is captured when set."""

        mock_posthog = MagicMock()
        mock_get_client.return_value = mock_posthog

        callback = PosthogTracingCallback()

        with callback.trace(assistant_chat_fixture, "Hello"):
            callback.set_trace_output("The answer is 42")

        call_args = mock_posthog.capture.call_args
        props = call_args.kwargs["properties"]
        assert props["$ai_output_state"] == {"answer": "The answer is 42"}

    @patch("baserow_enterprise.assistant.telemetry.get_posthog_client")
    def test_trace_sets_and_clears_context_var(
        self, mock_get_client, assistant_chat_fixture
    ):
        """Test that the ContextVar is set inside the trace and cleared after."""

        mock_get_client.return_value = MagicMock()

        callback = PosthogTracingCallback()

        # Before trace, context should be None
        assert _trace_ctx.get() is None

        with callback.trace(assistant_chat_fixture, "Hello"):
            ctx = _trace_ctx.get()
            assert ctx is not None
            assert ctx.trace_id == callback.trace_id
            assert ctx.user_id == str(assistant_chat_fixture.user_id)
            assert ctx.workspace_id == str(assistant_chat_fixture.workspace_id)
            assert ctx.chat_uuid == str(assistant_chat_fixture.uuid)

        # After trace, context should be cleared
        assert _trace_ctx.get() is None


class TestPydanticMessagesToPosthog:
    """Test the message format conversion utility."""

    def test_convert_text_message(self):
        """Test converting a simple text message."""

        messages = [{"role": "user", "parts": [{"type": "text", "content": "Hello"}]}]
        result = _pydantic_messages_to_posthog(messages)

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == [{"type": "text", "text": "Hello"}]

    def test_convert_tool_call(self):
        """Test converting a tool call message."""

        messages = [
            {
                "role": "assistant",
                "parts": [
                    {
                        "type": "tool_call",
                        "id": "call_123",
                        "name": "list_tables",
                        "arguments": {"database_id": 1},
                    }
                ],
            }
        ]
        result = _pydantic_messages_to_posthog(messages)

        assert result[0]["role"] == "assistant"
        tc = result[0]["content"][0]
        assert tc["type"] == "tool_call"
        assert tc["tool_call_id"] == "call_123"
        assert tc["name"] == "list_tables"
        assert tc["arguments"] == {"database_id": 1}

    def test_convert_tool_return(self):
        """Test converting a tool return message."""

        messages = [
            {
                "role": "tool",
                "parts": [
                    {
                        "type": "tool_return",
                        "tool_call_id": "call_123",
                        "content": "Tables: Users, Orders",
                    }
                ],
            }
        ]
        result = _pydantic_messages_to_posthog(messages)

        assert result[0]["content"][0]["type"] == "tool_result"
        assert result[0]["content"][0]["tool_call_id"] == "call_123"


class TestPosthogSpanProcessor:
    """Test the OpenTelemetry span processor for PostHog."""

    def _make_mock_span(
        self,
        name,
        kind,
        attrs=None,
        start_time=None,
        end_time=None,
        parent_span_id=None,
        span_id=0x1234,
    ):
        """Create a mock ReadableSpan."""

        span = MagicMock()
        span.name = name
        span.kind = kind
        span.attributes = attrs or {}
        span.start_time = start_time or 1000000000  # 1s in ns
        span.end_time = end_time or 2000000000  # 2s in ns
        span.events = []

        # Context
        span.context = MagicMock()
        span.context.span_id = span_id

        # Parent
        if parent_span_id is not None:
            span.parent = MagicMock()
            span.parent.span_id = parent_span_id
        else:
            span.parent = None

        return span

    @patch("baserow_enterprise.assistant.telemetry.get_posthog_client")
    def test_generation_span(self, mock_get_client):
        """Test that a 'chat' span is mapped to $ai_generation."""

        from opentelemetry.trace import SpanKind

        mock_posthog = MagicMock()
        mock_get_client.return_value = mock_posthog

        processor = PosthogSpanProcessor()

        span = self._make_mock_span(
            name="chat groq:llama-3.3-70b",
            kind=SpanKind.CLIENT,
            attrs={
                "gen_ai.request.model": "llama-3.3-70b",
                "gen_ai.response.model": "llama-3.3-70b",
                "gen_ai.provider.name": "groq",
                "gen_ai.usage.input_tokens": 100,
                "gen_ai.usage.output_tokens": 50,
                "gen_ai.input.messages": json.dumps(
                    [{"role": "user", "parts": [{"type": "text", "content": "Hi"}]}]
                ),
                "gen_ai.output.messages": json.dumps(
                    [
                        {
                            "role": "assistant",
                            "parts": [{"type": "text", "content": "Hello!"}],
                        }
                    ]
                ),
            },
            parent_span_id=0xABCD,
        )

        ctx = _TraceContext(
            trace_id="trace-123",
            user_id="user-456",
            workspace_id="ws-789",
            chat_uuid="chat-abc",
        )
        token = _trace_ctx.set(ctx)
        try:
            processor.on_end(span)
        finally:
            _trace_ctx.reset(token)

        mock_posthog.capture.assert_called_once()
        call = mock_posthog.capture.call_args
        assert call.kwargs["distinct_id"] == "user-456"
        assert call.kwargs["event"] == "$ai_generation"

        props = call.kwargs["properties"]
        assert props["$ai_trace_id"] == "trace-123"
        assert props["$ai_session_id"] == "chat-abc"
        assert props["workspace_id"] == "ws-789"
        assert props["$ai_model"] == "llama-3.3-70b"
        assert props["$ai_provider"] == "groq"
        assert props["$ai_input_tokens"] == 100
        assert props["$ai_output_tokens"] == 50
        assert props["$ai_latency"] == pytest.approx(1.0, abs=0.01)
        assert props["$ai_parent_id"] == f"{0xABCD:016x}"

        # Check message format conversion
        assert len(props["$ai_input"]) == 1
        assert props["$ai_input"][0]["role"] == "user"
        assert props["$ai_input"][0]["content"][0]["text"] == "Hi"

    @patch("baserow_enterprise.assistant.telemetry.get_posthog_client")
    def test_tool_span(self, mock_get_client):
        """Test that a 'running tool' span is mapped to $ai_span."""

        from opentelemetry.trace import SpanKind

        mock_posthog = MagicMock()
        mock_get_client.return_value = mock_posthog

        processor = PosthogSpanProcessor()

        span = self._make_mock_span(
            name="running tool",
            kind=SpanKind.INTERNAL,
            attrs={
                "gen_ai.tool.name": "list_tables",
                "tool_arguments": '{"database_id": 1}',
                "tool_response": "Found 3 tables: Users, Orders, Products",
            },
            parent_span_id=0x5678,
        )

        ctx = _TraceContext(
            trace_id="trace-123",
            user_id="user-456",
            workspace_id="ws-789",
            chat_uuid="chat-abc",
        )
        token = _trace_ctx.set(ctx)
        try:
            processor.on_end(span)
        finally:
            _trace_ctx.reset(token)

        mock_posthog.capture.assert_called_once()
        call = mock_posthog.capture.call_args
        assert call.kwargs["event"] == "$ai_span"

        props = call.kwargs["properties"]
        assert props["$ai_span_name"] == "Tool: list_tables"
        assert props["$ai_input_state"] == {"database_id": 1}
        assert "Found 3 tables" in props["$ai_output_state"]
        assert props["$ai_latency"] == pytest.approx(1.0, abs=0.01)

    @patch("baserow_enterprise.assistant.telemetry.get_posthog_client")
    def test_agent_run_span_is_exported(self, mock_get_client):
        """Test that 'agent run' spans are exported as $ai_span with agent name,
        system prompt, user input, and final output."""

        from opentelemetry.trace import SpanKind

        mock_posthog = MagicMock()
        mock_get_client.return_value = mock_posthog

        processor = PosthogSpanProcessor()

        system_instructions = json.dumps(
            [{"type": "text", "content": "You are a helpful assistant."}]
        )
        all_messages = json.dumps(
            [
                {
                    "role": "user",
                    "parts": [{"type": "text", "content": "Create a table"}],
                },
                {
                    "role": "model-response",
                    "parts": [{"type": "text", "content": "Done!"}],
                },
            ]
        )

        span = self._make_mock_span(
            name="agent run",
            kind=SpanKind.INTERNAL,
            attrs={
                "agent_name": "main_agent",
                "gen_ai.system_instructions": system_instructions,
                "pydantic_ai.all_messages": all_messages,
                "final_result": '{"table_id": 1}',
            },
            parent_span_id=0x9999,
        )

        ctx = _TraceContext(
            trace_id="trace-123",
            user_id="user-456",
            workspace_id="ws-789",
            chat_uuid="chat-abc",
        )
        token = _trace_ctx.set(ctx)
        try:
            processor.on_end(span)
        finally:
            _trace_ctx.reset(token)

        mock_posthog.capture.assert_called_once()
        call = mock_posthog.capture.call_args
        assert call.kwargs["event"] == "$ai_span"

        props = call.kwargs["properties"]
        assert props["$ai_span_name"] == "Agent: main_agent"
        assert props["$ai_trace_id"] == "trace-123"
        assert props["$ai_latency"] == pytest.approx(1.0, abs=0.01)
        assert props["$ai_parent_id"] == f"{0x9999:016x}"
        assert (
            props["$ai_input_state"]["system_prompt"] == "You are a helpful assistant."
        )
        assert props["$ai_input_state"]["user_prompt"] == "Create a table"
        assert props["$ai_output_state"] == {"table_id": 1}

    @patch("baserow_enterprise.assistant.telemetry.get_posthog_client")
    def test_agent_run_span_subagent_label(self, mock_get_client):
        """Test that sub-agent spans get their own distinct label and handle
        string final_result."""

        from opentelemetry.trace import SpanKind

        mock_posthog = MagicMock()
        mock_get_client.return_value = mock_posthog

        processor = PosthogSpanProcessor()

        span = self._make_mock_span(
            name="agent run",
            kind=SpanKind.INTERNAL,
            attrs={
                "agent_name": "sample_row_agent",
                "final_result": "Rows created successfully",
            },
        )

        ctx = _TraceContext(
            trace_id="trace-123",
            user_id="user-456",
            workspace_id="ws-789",
            chat_uuid="chat-abc",
        )
        token = _trace_ctx.set(ctx)
        try:
            processor.on_end(span)
        finally:
            _trace_ctx.reset(token)

        props = mock_posthog.capture.call_args.kwargs["properties"]
        assert props["$ai_span_name"] == "Agent: sample_row_agent"
        assert props["$ai_output_state"] == "Rows created successfully"

    @patch("baserow_enterprise.assistant.telemetry.get_posthog_client")
    def test_running_tools_skipped_and_parent_remapped(self, mock_get_client):
        """Test that 'running tools' is not emitted and child tool spans
        have their parent remapped to the grandparent (agent span)."""

        from opentelemetry.trace import SpanKind

        mock_posthog = MagicMock()
        mock_get_client.return_value = mock_posthog

        processor = PosthogSpanProcessor()

        agent_span_id = 0xAAAA
        tools_group_span_id = 0xBBBB
        tool_span_id = 0xCCCC

        # 1) "running tools" starts — processor records the parent mapping.
        tools_group_span = self._make_mock_span(
            name="running tools",
            kind=SpanKind.INTERNAL,
            span_id=tools_group_span_id,
            parent_span_id=agent_span_id,
        )
        processor.on_start(tools_group_span)

        # 2) "running tool" ends — its direct parent is the tools group,
        #    but the processor should remap to the agent span.
        tool_span = self._make_mock_span(
            name="running tool",
            kind=SpanKind.INTERNAL,
            attrs={
                "gen_ai.tool.name": "create_tables",
                "tool_arguments": "{}",
                "tool_response": "ok",
            },
            span_id=tool_span_id,
            parent_span_id=tools_group_span_id,
        )

        ctx = _TraceContext(trace_id="t", user_id="u", workspace_id="w", chat_uuid="c")
        token = _trace_ctx.set(ctx)
        try:
            processor.on_end(tool_span)

            # Tool span's parent should be the agent, not the tools group.
            props = mock_posthog.capture.call_args.kwargs["properties"]
            assert props["$ai_parent_id"] == f"{agent_span_id:016x}"

            mock_posthog.capture.reset_mock()

            # 3) "running tools" ends — should NOT emit anything.
            processor.on_end(tools_group_span)
            mock_posthog.capture.assert_not_called()
        finally:
            _trace_ctx.reset(token)

    @patch("baserow_enterprise.assistant.telemetry.get_posthog_client")
    def test_without_trace_context_is_noop(self, mock_get_client):
        """Test that spans without a trace context are silently ignored."""

        from opentelemetry.trace import SpanKind

        mock_posthog = MagicMock()
        mock_get_client.return_value = mock_posthog

        processor = PosthogSpanProcessor()

        span = self._make_mock_span(
            name="chat groq:llama-3.3-70b",
            kind=SpanKind.CLIENT,
        )

        # No trace context set
        processor.on_end(span)

        mock_posthog.capture.assert_not_called()

    @patch("baserow_enterprise.assistant.telemetry.get_posthog_client")
    def test_multiple_spans(self, mock_get_client):
        """Test that multiple spans are all processed."""

        from opentelemetry.trace import SpanKind

        mock_posthog = MagicMock()
        mock_get_client.return_value = mock_posthog

        processor = PosthogSpanProcessor()

        generation_span = self._make_mock_span(
            name="chat openai:gpt-4o",
            kind=SpanKind.CLIENT,
            attrs={
                "gen_ai.request.model": "gpt-4o",
                "gen_ai.provider.name": "openai",
                "gen_ai.usage.input_tokens": 200,
                "gen_ai.usage.output_tokens": 80,
            },
            span_id=0x1111,
        )
        tool_span = self._make_mock_span(
            name="running tool",
            kind=SpanKind.INTERNAL,
            attrs={
                "gen_ai.tool.name": "create_table",
                "tool_arguments": "{}",
                "tool_response": "Created table",
            },
            span_id=0x2222,
        )

        ctx = _TraceContext(
            trace_id="trace-multi",
            user_id="user-1",
            workspace_id="ws-1",
            chat_uuid="chat-1",
        )
        token = _trace_ctx.set(ctx)
        try:
            processor.on_end(generation_span)
            processor.on_end(tool_span)
        finally:
            _trace_ctx.reset(token)

        assert mock_posthog.capture.call_count == 2
        events = [c.kwargs["event"] for c in mock_posthog.capture.call_args_list]
        assert "$ai_generation" in events
        assert "$ai_span" in events


class TestSetupInstrumentation:
    """Test the one-time instrumentation setup."""

    @patch("baserow_enterprise.assistant.telemetry._instrumentation_ready", False)
    @patch("baserow_enterprise.assistant.telemetry.get_posthog_client")
    def test_setup_skipped_when_posthog_disabled(self, mock_get_client):
        """Test that setup is skipped when POSTHOG_ENABLED is False."""

        from baserow_enterprise.assistant.telemetry import setup_instrumentation

        # POSTHOG_ENABLED is False in test settings
        setup_instrumentation()

        # Should not have called get_posthog_client (nothing was set up)
        mock_get_client.assert_not_called()


class TestEndToEndOtelPipeline:
    """Integration: verify that a real pydantic-ai Agent run produces
    PostHog events via the OTel span exporter."""

    @patch("baserow_enterprise.assistant.telemetry.get_posthog_client")
    def test_agent_run_produces_posthog_events(self, mock_get_client):
        """A real Agent.run_sync() inside a trace() should emit both
        $ai_trace and $ai_generation events via PostHog."""

        from opentelemetry.sdk.trace import TracerProvider as _TP
        from pydantic_ai import Agent, InstrumentationSettings

        mock_posthog = MagicMock()
        mock_get_client.return_value = mock_posthog

        # Wire up the same pipeline that setup_instrumentation() creates.
        tp = _TP()
        tp.add_span_processor(PosthogSpanProcessor())
        Agent.instrument_all(
            InstrumentationSettings(tracer_provider=tp, include_content=True)
        )

        try:
            # Set trace context (simulates PosthogTracingCallback.trace()).
            ctx = _TraceContext(
                trace_id="e2e-trace",
                user_id="e2e-user",
                workspace_id="e2e-ws",
                chat_uuid="e2e-chat",
            )
            tok = _trace_ctx.set(ctx)
            tools_tok = _tool_calls.set([])

            try:
                agent = Agent(
                    output_type=str,
                    instructions="Reply with 'pong'.",
                    name="e2e_test_agent",
                )
                agent.run_sync("ping", model="test")
            finally:
                _trace_ctx.reset(tok)
                _tool_calls.reset(tools_tok)

            # Verify PostHog received at least one $ai_generation event.
            events = [c.kwargs["event"] for c in mock_posthog.capture.call_args_list]
            assert "$ai_generation" in events, (
                f"Expected $ai_generation in captured events, got: {events}"
            )

            # Verify the trace metadata was attached.
            gen_call = next(
                c
                for c in mock_posthog.capture.call_args_list
                if c.kwargs["event"] == "$ai_generation"
            )
            props = gen_call.kwargs["properties"]
            assert props["$ai_trace_id"] == "e2e-trace"
            assert props["$ai_session_id"] == "e2e-chat"
            assert props["workspace_id"] == "e2e-ws"
        finally:
            # Clean up global instrumentation so other tests aren't affected.
            Agent.instrument_all(None)
