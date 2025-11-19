from unittest.mock import MagicMock, patch

import pytest
import udspy
from posthog.ai.openai import AsyncOpenAI

from baserow_enterprise.assistant.models import AssistantChat
from baserow_enterprise.assistant.telemetry import PosthogTracingCallback


@pytest.fixture
def assistant_chat_fixture(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    return AssistantChat.objects.create(
        user=user, workspace=workspace, title="Test Chat"
    )


@pytest.mark.django_db
class TestPosthogTracingCallback:
    @patch("baserow_enterprise.assistant.telemetry.posthog_client")
    @patch("baserow_enterprise.assistant.telemetry.settings")
    @patch("baserow_enterprise.assistant.telemetry.udspy")
    def test_trace_context_manager_success(
        self, mock_udspy, mock_settings, mock_posthog, assistant_chat_fixture
    ):
        """Test the trace context manager in a successful execution flow."""

        mock_settings.POSTHOG_ENABLED = True
        callback = PosthogTracingCallback()

        # Mock the udspy context lm
        mock_lm = MagicMock()
        mock_lm.client = MagicMock()
        mock_lm.client.api_key = "test-api-key"
        mock_lm.client.base_url = "https://api.test.com"
        # Ensure it's not already an AsyncOpenAI instance so patching logic runs
        mock_lm.client.__class__ = MagicMock

        mock_context_lm = MagicMock()
        mock_context_lm.get.return_value = mock_lm
        mock_udspy.settings._context_lm = mock_context_lm

        with callback.trace(assistant_chat_fixture, "Hello"):
            assert callback.trace_id is not None
            assert callback.span_id is not None
            assert callback.user_id == str(assistant_chat_fixture.user_id)

            # Verify LM client was patched
            assert isinstance(mock_lm.client, AsyncOpenAI)

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
        assert props["$ai_input_state"] == "Hello"

    @patch("baserow_enterprise.assistant.telemetry.posthog_client")
    @patch("baserow_enterprise.assistant.telemetry.settings")
    @patch("baserow_enterprise.assistant.telemetry.udspy")
    def test_trace_context_manager_exception(
        self, mock_udspy, mock_settings, mock_posthog, assistant_chat_fixture
    ):
        """Test the trace context manager when an exception occurs."""

        mock_settings.POSTHOG_ENABLED = True
        callback = PosthogTracingCallback()

        mock_lm = MagicMock()
        mock_lm.client = MagicMock()
        mock_lm.client.api_key = "test-api-key"
        mock_lm.client.base_url = "https://api.test.com"
        mock_context_lm = MagicMock()
        mock_context_lm.get.return_value = mock_lm
        mock_udspy.settings._context_lm = mock_context_lm

        with pytest.raises(ValueError):
            with callback.trace(assistant_chat_fixture, "Hello"):
                raise ValueError("Test error")

        # Verify trace event captured with error
        call_args = mock_posthog.capture.call_args
        assert call_args is not None
        assert call_args.kwargs["event"] == "$ai_trace"
        assert call_args.kwargs["properties"]["$ai_is_error"] is True

    @patch("baserow_enterprise.assistant.telemetry.posthog_client")
    def test_on_module_start_end(self, mock_posthog, assistant_chat_fixture):
        """Test module execution tracing."""

        callback = PosthogTracingCallback()
        # Initialize context manually
        callback.chat = assistant_chat_fixture
        callback.user_id = str(assistant_chat_fixture.user_id)
        callback.workspace_id = str(assistant_chat_fixture.workspace_id)
        callback.chat_uuid = str(assistant_chat_fixture.uuid)
        callback.trace_id = "trace-123"
        callback.span_ids = ["root-span"]
        callback.spans = {}
        callback.enabled = True

        # Mock a CoT module
        mock_module = MagicMock(spec=udspy.ChainOfThought)
        mock_module.__class__ = udspy.ChainOfThought
        mock_signature = MagicMock()
        mock_signature.get_input_fields.return_value = {"q": 1}
        mock_signature.get_output_fields.return_value = {
            "a": 1
        }  # Should be dict, not list
        mock_signature.get_instructions.return_value = "Test instructions"
        mock_module.original_signature = mock_signature

        # Start module
        callback.on_module_start(
            call_id="call-1", instance=mock_module, inputs={"kwargs": {"q": "test"}}
        )

        assert len(callback.span_ids) == 2
        assert len(callback.spans) == 1

        # End module
        callback.on_module_end(
            call_id="call-1", outputs={"a": "result"}, exception=None
        )

        assert len(callback.span_ids) == 1
        assert len(callback.spans) == 0

        # Verify span event was called
        mock_posthog.capture.assert_called_once()
        call_args = mock_posthog.capture.call_args

        # Check the event structure
        assert call_args.kwargs["distinct_id"] == str(assistant_chat_fixture.user_id)
        assert call_args.kwargs["event"] == "$ai_span"
        assert "timestamp" in call_args.kwargs

        # Check properties
        props = call_args.kwargs["properties"]
        assert props["$ai_trace_id"] == "trace-123"
        assert props["$ai_session_id"] == str(assistant_chat_fixture.uuid)
        assert props["workspace_id"] == str(assistant_chat_fixture.workspace_id)
        assert props["$ai_span_name"] == "ChainOfThought"
        assert props["$ai_span_id"] == "call-1"
        assert props["$ai_parent_span_id"] == "root-span"
        assert "$ai_input_state" in props
        assert props["$ai_output_state"] == {"a": "result"}
        assert props["$ai_latency"] >= 0
        assert props["$ai_is_error"] is False

    def test_on_lm_start(self, assistant_chat_fixture):
        """Test LM start tracing."""

        callback = PosthogTracingCallback()
        callback.chat = assistant_chat_fixture
        callback.user_id = "user-1"
        callback.workspace_id = "ws-1"
        callback.chat_uuid = "chat-1"
        callback.trace_id = "trace-1"
        callback.span_ids = ["root"]

        mock_lm = MagicMock()
        mock_lm.provider = "openai"

        inputs = {"kwargs": {}}
        callback.on_lm_start("call-1", mock_lm, inputs)

        assert len(callback.span_ids) == 2
        assert inputs["kwargs"]["posthog_distinct_id"] == "user-1"
        assert inputs["kwargs"]["posthog_trace_id"] == "trace-1"
        assert inputs["kwargs"]["posthog_properties"]["$ai_provider"] == "openai"

    @patch("baserow_enterprise.assistant.telemetry.posthog_client")
    def test_on_tool_start_end(self, mock_posthog, assistant_chat_fixture):
        """Test tool execution tracing."""

        callback = PosthogTracingCallback()
        callback.chat = assistant_chat_fixture
        callback.user_id = str(assistant_chat_fixture.user_id)
        callback.workspace_id = str(assistant_chat_fixture.workspace_id)
        callback.chat_uuid = str(assistant_chat_fixture.uuid)
        callback.trace_id = "trace-1"
        callback.span_ids = ["root"]
        callback.spans = {}
        callback.enabled = True

        mock_tool = MagicMock()
        mock_tool.name = "test_tool"

        # Start tool
        callback.on_tool_start(
            call_id="call-1", instance=mock_tool, inputs={"arg": "val"}
        )

        assert len(callback.spans) == 1

        # End tool
        callback.on_tool_end(call_id="call-1", outputs="result", exception=None)

        # Verify event
        mock_posthog.capture.assert_called()
        props = mock_posthog.capture.call_args.kwargs["properties"]
        assert props["$ai_span_name"] == "Tool: test_tool"
        assert props["$ai_input_state"] == {"arg": "val"}
        assert props["$ai_output_state"] == "result"

    @patch("baserow_enterprise.assistant.telemetry.posthog_client")
    def test_on_module_end_with_exception(self, mock_posthog, assistant_chat_fixture):
        """Test that exception string is captured in $ai_output_state."""

        callback = PosthogTracingCallback()
        callback.chat = assistant_chat_fixture
        callback.user_id = str(assistant_chat_fixture.user_id)
        callback.workspace_id = str(assistant_chat_fixture.workspace_id)
        callback.chat_uuid = str(assistant_chat_fixture.uuid)
        callback.trace_id = "trace-123"
        callback.span_ids = ["root-span"]
        callback.spans = {}
        callback.enabled = True

        # Mock a module
        mock_module = MagicMock(spec=udspy.ChainOfThought)
        mock_module.__class__ = udspy.ChainOfThought
        mock_signature = MagicMock()
        mock_signature.get_input_fields.return_value = {"q": 1}
        mock_signature.get_output_fields.return_value = {"a": 1}
        mock_signature.get_instructions.return_value = "Test instructions"
        mock_module.original_signature = mock_signature

        # Start module
        callback.on_module_start(
            call_id="call-1", instance=mock_module, inputs={"kwargs": {"q": "test"}}
        )

        # End module with exception
        test_exception = ValueError("Test error message")
        callback.on_module_end(call_id="call-1", outputs=None, exception=test_exception)

        # Verify exception string is captured
        mock_posthog.capture.assert_called_once()
        call_args = mock_posthog.capture.call_args
        props = call_args.kwargs["properties"]

        assert props["$ai_is_error"] is True
        assert props["$ai_output_state"] == "Test error message"

    @patch("baserow_enterprise.assistant.telemetry.posthog_client")
    def test_on_tool_end_with_exception(self, mock_posthog, assistant_chat_fixture):
        """Test that exception string is captured in $ai_output_state for tools."""

        callback = PosthogTracingCallback()
        callback.chat = assistant_chat_fixture
        callback.user_id = str(assistant_chat_fixture.user_id)
        callback.workspace_id = str(assistant_chat_fixture.workspace_id)
        callback.chat_uuid = str(assistant_chat_fixture.uuid)
        callback.trace_id = "trace-1"
        callback.span_ids = ["root"]
        callback.spans = {}
        callback.enabled = True

        mock_tool = MagicMock()
        mock_tool.name = "test_tool"

        # Start tool
        callback.on_tool_start(
            call_id="call-1", instance=mock_tool, inputs={"arg": "val"}
        )

        # End tool with exception
        test_exception = RuntimeError("Tool execution failed")
        callback.on_tool_end(call_id="call-1", outputs=None, exception=test_exception)

        # Verify exception string is captured
        mock_posthog.capture.assert_called_once()
        call_args = mock_posthog.capture.call_args
        props = call_args.kwargs["properties"]

        assert props["$ai_is_error"] is True
        assert props["$ai_output_state"] == "Tool execution failed"

    @patch("baserow_enterprise.assistant.telemetry.posthog_client")
    def test_telemetry_disabled(self, mock_posthog, assistant_chat_fixture):
        """Test that nothing is captured when disabled."""

        callback = PosthogTracingCallback()
        callback.enabled = False

        callback._capture_event("test_event")

        mock_posthog.capture.assert_not_called()
