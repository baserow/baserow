"""Unit tests for RetryingModel."""

import os

import pytest

from baserow_enterprise.assistant.retrying_model import (
    RetryingModel,
    _is_transient_provider_error,
    _resolve_credentials,
    _resolve_model,
)


class TestIsTransientProviderError:
    def test_groq_parse_error(self):
        exc = Exception("Failed to parse tool call arguments as JSON")
        assert _is_transient_provider_error(exc) is True

    def test_tool_validation_failed(self):
        exc = Exception("Tool call validation failed: something")
        assert _is_transient_provider_error(exc) is True

    def test_auth_error_not_retryable(self):
        exc = Exception("Invalid API key")
        assert _is_transient_provider_error(exc) is False

    def test_generic_error_not_retryable(self):
        exc = ValueError("something went wrong")
        assert _is_transient_provider_error(exc) is False


def _make_retrying(inner_mock, **kwargs):
    """Create a RetryingModel with a pre-resolved mock as the wrapped model."""

    model = RetryingModel.__new__(RetryingModel)
    model._wrapped_or_name = inner_mock
    model._resolved = inner_mock
    model.max_attempts = kwargs.get("max_attempts", 3)
    model.base_delay = kwargs.get("base_delay", 0.01)
    model.max_delay = kwargs.get("max_delay", 10.0)
    return model


@pytest.mark.asyncio
async def test_request_retries_on_transient_error():
    """RetryingModel.request should retry transient errors."""

    from unittest.mock import AsyncMock, MagicMock

    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.models import ModelRequestParameters

    inner = MagicMock()
    response = ModelResponse(parts=[TextPart(content="hello")])
    inner.request = AsyncMock(
        side_effect=[
            Exception("Failed to parse tool call arguments as JSON"),
            response,
        ]
    )

    model = _make_retrying(inner)
    result = await model.request(
        [], None, ModelRequestParameters(function_tools=[], output_tools=[])
    )

    assert result == response
    assert inner.request.call_count == 2


@pytest.mark.asyncio
async def test_request_raises_non_transient_error():
    """RetryingModel.request should not retry non-transient errors."""

    from unittest.mock import AsyncMock, MagicMock

    from pydantic_ai.models import ModelRequestParameters

    inner = MagicMock()
    inner.request = AsyncMock(side_effect=ValueError("bad input"))

    model = _make_retrying(inner)
    with pytest.raises(ValueError, match="bad input"):
        await model.request(
            [], None, ModelRequestParameters(function_tools=[], output_tools=[])
        )

    assert inner.request.call_count == 1


@pytest.mark.asyncio
async def test_request_exhausts_retries():
    """RetryingModel should raise after exhausting max_attempts."""

    from unittest.mock import AsyncMock, MagicMock

    from pydantic_ai.models import ModelRequestParameters

    inner = MagicMock()
    inner.request = AsyncMock(
        side_effect=Exception("Failed to parse tool call arguments as JSON")
    )

    model = _make_retrying(inner, max_attempts=2)
    with pytest.raises(Exception, match="Failed to parse"):
        await model.request(
            [], None, ModelRequestParameters(function_tools=[], output_tools=[])
        )

    assert inner.request.call_count == 2


def test_deferred_model_resolution():
    """RetryingModel should defer infer_model until first access."""

    model = RetryingModel("groq:some-model")
    # Should not raise at construction time
    assert model._resolved is None


# ---------------------------------------------------------------------------
# tool_use_failed recovery
# ---------------------------------------------------------------------------


def _make_tool_use_failed_error(
    failed_generation: str,
    model_name: str = "test-model",
):
    from pydantic_ai.exceptions import ModelHTTPError

    return ModelHTTPError(
        status_code=400,
        model_name=model_name,
        body={
            "error": {
                "message": "Failed to parse tool call arguments as JSON",
                "type": "invalid_request_error",
                "code": "tool_use_failed",
                "failed_generation": failed_generation,
            }
        },
    )


class TestTryRecoverToolUseFailed:
    def test_recovers_valid_tool_call(self):
        from pydantic_ai.messages import ToolCallPart

        from baserow_enterprise.assistant.retrying_model import (
            _try_recover_tool_use_failed,
        )

        exc = _make_tool_use_failed_error(
            '{"name": "list_tables", "arguments": {"thought": "test"}}'
        )
        result = _try_recover_tool_use_failed(exc)

        assert result is not None
        assert len(result.parts) == 1
        part = result.parts[0]
        assert isinstance(part, ToolCallPart)
        assert part.tool_name == "list_tables"
        assert "thought" in part.args

    def test_recovers_malformed_json_as_tool_call(self):
        from baserow_enterprise.assistant.retrying_model import (
            _try_recover_tool_use_failed,
        )

        exc = _make_tool_use_failed_error("{not valid json")
        result = _try_recover_tool_use_failed(exc)

        assert result is not None
        assert len(result.parts) == 1
        from pydantic_ai.messages import ToolCallPart

        assert isinstance(result.parts[0], ToolCallPart)
        assert result.parts[0].tool_name == "unknown"
        assert result.parts[0].args == "{}"

    def test_recovers_malformed_json_extracts_tool_name(self):
        from baserow_enterprise.assistant.retrying_model import (
            _try_recover_tool_use_failed,
        )

        exc = _make_tool_use_failed_error(
            '{"name": "create_elements", "arguments": {"page_id": 1, "elements": [truncated'
        )
        result = _try_recover_tool_use_failed(exc)

        assert result is not None
        from pydantic_ai.messages import ToolCallPart

        assert isinstance(result.parts[0], ToolCallPart)
        assert result.parts[0].tool_name == "create_elements"
        assert result.parts[0].args == "{}"

    def test_returns_none_for_non_tool_use_failed(self):
        from pydantic_ai.exceptions import ModelHTTPError

        from baserow_enterprise.assistant.retrying_model import (
            _try_recover_tool_use_failed,
        )

        exc = ModelHTTPError(
            status_code=400,
            model_name="test",
            body={"error": {"message": "other error", "code": "other"}},
        )
        assert _try_recover_tool_use_failed(exc) is None

    def test_returns_none_for_non_model_http_error(self):
        from baserow_enterprise.assistant.retrying_model import (
            _try_recover_tool_use_failed,
        )

        assert _try_recover_tool_use_failed(ValueError("nope")) is None

    def test_recovers_raw_api_error_with_body(self):
        """Handles raw provider APIError (e.g. groq.APIError) with body attr."""

        from pydantic_ai.messages import ToolCallPart

        from baserow_enterprise.assistant.retrying_model import (
            _try_recover_tool_use_failed,
        )

        class FakeAPIError(Exception):
            def __init__(self, message, body=None):
                super().__init__(message)
                self.body = body

        exc = FakeAPIError(
            "Failed to parse tool call arguments as JSON",
            body={
                "message": "Failed to parse tool call arguments as JSON",
                "type": "invalid_request_error",
                "code": "tool_use_failed",
                "failed_generation": '{"name": "create_rows", "arguments": {"table_id": 1}}',
            },
        )
        result = _try_recover_tool_use_failed(exc)
        assert result is not None
        assert isinstance(result.parts[0], ToolCallPart)
        assert result.parts[0].tool_name == "create_rows"


@pytest.mark.asyncio
async def test_request_recovers_tool_use_failed():
    """request() should recover tool_use_failed into a ModelResponse."""

    from unittest.mock import AsyncMock, MagicMock

    from pydantic_ai.models import ModelRequestParameters

    inner = MagicMock()
    inner.request = AsyncMock(
        side_effect=_make_tool_use_failed_error(
            '{"name": "create_rows", "arguments": {"thought": "hi"}}'
        )
    )

    model = _make_retrying(inner)
    result = await model.request(
        [], None, ModelRequestParameters(function_tools=[], output_tools=[])
    )

    from pydantic_ai.messages import ToolCallPart

    # Should return a recovered response, not raise
    assert len(result.parts) == 1
    assert isinstance(result.parts[0], ToolCallPart)
    assert result.parts[0].tool_name == "create_rows"
    # Should NOT have retried — recovery is immediate
    assert inner.request.call_count == 1


@pytest.mark.asyncio
async def test_request_stream_recovers_tool_use_failed():
    """request_stream() should recover tool_use_failed into a PreFetchedResponse."""

    from unittest.mock import MagicMock

    from pydantic_ai.models import ModelRequestParameters

    inner = MagicMock()

    async def _failing_stream(*args, **kwargs):
        raise _make_tool_use_failed_error(
            '{"name": "list_rows", "arguments": {"table_id": 1}}'
        )

    # Make request_stream an async context manager that raises
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def failing_cm(*args, **kwargs):
        raise _make_tool_use_failed_error(
            '{"name": "list_rows", "arguments": {"table_id": 1}}'
        )
        yield  # pragma: no cover

    inner.request_stream = failing_cm

    model = _make_retrying(inner)
    async with model.request_stream(
        [], None, ModelRequestParameters(function_tools=[], output_tools=[])
    ) as stream:
        # Collect events from the pre-fetched response
        events = [e async for e in stream]

    from pydantic_ai.models import PartStartEvent

    start_events = [e for e in events if isinstance(e, PartStartEvent)]
    assert len(start_events) == 1
    assert start_events[0].part.tool_name == "list_rows"


@pytest.mark.asyncio
async def test_request_stream_recovers_mid_stream_api_error():
    """_ErrorRecoveringStream catches APIError during chunk iteration
    and emits recovery events instead of crashing."""

    from contextlib import asynccontextmanager
    from unittest.mock import MagicMock

    from pydantic_ai._parts_manager import ModelResponsePartsManager
    from pydantic_ai.models import ModelRequestParameters, PartStartEvent

    # Simulate a real StreamedResponse whose _get_event_iterator raises APIError
    class FakeAPIError(Exception):
        """Simulates groq.APIError with a body attribute."""

        def __init__(self, message, body=None):
            super().__init__(message)
            self.body = body

    class FakeStreamedResponse:
        """Minimal fake that raises during iteration."""

        model_name = "test-model"
        provider_name = "test"
        provider_url = "http://test"
        timestamp = None
        _parts_manager = ModelResponsePartsManager()
        model_request_parameters = ModelRequestParameters(
            function_tools=[], output_tools=[]
        )
        final_result_event = None
        provider_response_id = None
        provider_details = None
        finish_reason = None

        async def _get_event_iterator(self):
            raise FakeAPIError(
                "Failed to parse tool call arguments as JSON",
                body={
                    "message": "Failed to parse tool call arguments as JSON",
                    "type": "invalid_request_error",
                    "code": "tool_use_failed",
                    "failed_generation": '{"name": "create_elements", "arguments": {"bad": true}}',
                },
            )
            yield  # pragma: no cover — make it a generator

    inner = MagicMock()

    @asynccontextmanager
    async def fake_request_stream(*args, **kwargs):
        yield FakeStreamedResponse()

    inner.request_stream = fake_request_stream

    model = _make_retrying(inner)
    async with model.request_stream(
        [], None, ModelRequestParameters(function_tools=[], output_tools=[])
    ) as stream:
        events = [e async for e in stream]

    start_events = [e for e in events if isinstance(e, PartStartEvent)]
    assert len(start_events) == 1
    assert start_events[0].part.tool_name == "create_elements"


@pytest.mark.asyncio
async def test_request_stream_recovers_mid_stream_malformed_json():
    """_ErrorRecoveringStream recovers even when failed_generation JSON is
    unparseable — returns a ToolCallPart with empty args so pydantic-ai's
    validation loop can retry."""

    from contextlib import asynccontextmanager
    from unittest.mock import MagicMock

    from pydantic_ai._parts_manager import ModelResponsePartsManager
    from pydantic_ai.messages import ToolCallPart
    from pydantic_ai.models import ModelRequestParameters, PartStartEvent

    class FakeAPIError(Exception):
        def __init__(self, message, body=None):
            super().__init__(message)
            self.body = body

    class FakeStreamedResponse:
        model_name = "test-model"
        provider_name = "test"
        provider_url = "http://test"
        timestamp = None
        _parts_manager = ModelResponsePartsManager()
        model_request_parameters = ModelRequestParameters(
            function_tools=[], output_tools=[]
        )
        final_result_event = None
        provider_response_id = None
        provider_details = None
        finish_reason = None

        async def _get_event_iterator(self):
            raise FakeAPIError(
                "Failed to parse tool call arguments as JSON",
                body={
                    "message": "Failed to parse tool call arguments as JSON",
                    "type": "invalid_request_error",
                    "code": "tool_use_failed",
                    "failed_generation": '{"name": "create_elements", "arguments": {truncated',
                },
            )
            yield  # pragma: no cover

    inner = MagicMock()

    @asynccontextmanager
    async def fake_request_stream(*args, **kwargs):
        yield FakeStreamedResponse()

    inner.request_stream = fake_request_stream

    model = _make_retrying(inner)
    async with model.request_stream(
        [], None, ModelRequestParameters(function_tools=[], output_tools=[])
    ) as stream:
        events = [e async for e in stream]

    start_events = [e for e in events if isinstance(e, PartStartEvent)]
    assert len(start_events) == 1
    assert isinstance(start_events[0].part, ToolCallPart)
    assert start_events[0].part.tool_name == "create_elements"
    assert start_events[0].part.args == "{}"


@pytest.mark.asyncio
async def test_request_stream_reraises_after_yield():
    """Errors during stream __aexit__ (non-recoverable) must re-raise."""

    from contextlib import asynccontextmanager
    from unittest.mock import MagicMock

    from pydantic_ai.models import ModelRequestParameters

    inner = MagicMock()

    @asynccontextmanager
    async def stream_that_fails_during_consumption(*args, **kwargs):
        # Yield a mock stream, then raise on __aexit__
        yield MagicMock()
        raise Exception("some unrelated error")

    inner.request_stream = stream_that_fails_during_consumption

    model = _make_retrying(inner)
    with pytest.raises(Exception, match="some unrelated error"):
        async with model.request_stream(
            [], None, ModelRequestParameters(function_tools=[], output_tools=[])
        ) as stream:
            pass  # stream consumed, then __aexit__ raises


# ---------------------------------------------------------------------------
# Credential resolution & model dispatch
# ---------------------------------------------------------------------------


class TestResolveCredentials:
    """Tests for _resolve_credentials env-var precedence."""

    def test_provider_specific_key_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "groq-key")
        monkeypatch.setenv("UDSPY_LM_API_KEY", "udspy-key")

        creds = _resolve_credentials("groq")
        assert creds["api_key"] == "groq-key"

    def test_falls_back_to_udspy_api_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.setenv("UDSPY_LM_API_KEY", "udspy-key")

        creds = _resolve_credentials("groq")
        assert creds["api_key"] == "udspy-key"

    def test_provider_specific_base_url_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("OPENAI_BASE_URL", "https://custom.openai.com")
        monkeypatch.setenv("UDSPY_LM_OPENAI_COMPATIBLE_BASE_URL", "https://udspy.com")

        creds = _resolve_credentials("openai")
        assert creds["base_url"] == "https://custom.openai.com"

    def test_falls_back_to_udspy_base_url(self, monkeypatch):
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.setenv("UDSPY_LM_OPENAI_COMPATIBLE_BASE_URL", "https://udspy.com")

        creds = _resolve_credentials("openai")
        assert creds["base_url"] == "https://udspy.com"

    def test_returns_none_when_nothing_set(self, monkeypatch):
        for var in (
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "UDSPY_LM_API_KEY",
            "UDSPY_LM_OPENAI_COMPATIBLE_BASE_URL",
        ):
            monkeypatch.delenv(var, raising=False)

        creds = _resolve_credentials("openai")
        assert creds["api_key"] is None
        assert creds["base_url"] is None

    def test_unknown_provider_still_gets_udspy_fallback(self, monkeypatch):
        monkeypatch.setenv("UDSPY_LM_API_KEY", "udspy-key")

        creds = _resolve_credentials("some_unknown_provider")
        assert creds["api_key"] == "udspy-key"

    def test_never_mutates_os_environ(self, monkeypatch):
        monkeypatch.setenv("UDSPY_LM_API_KEY", "udspy-key")
        monkeypatch.setenv("UDSPY_LM_OPENAI_COMPATIBLE_BASE_URL", "https://udspy.com")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        snapshot = dict(os.environ)

        _resolve_credentials("openai")
        _resolve_credentials("groq")
        _resolve_credentials("anthropic")

        assert dict(os.environ) == snapshot


class TestResolveModel:
    """Tests for _resolve_model provider dispatch."""

    def test_openai_prefix(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        from pydantic_ai.models.openai import OpenAIChatModel

        model = _resolve_model("openai:gpt-4o")
        assert isinstance(model, OpenAIChatModel)

    def test_groq_prefix(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
        from pydantic_ai.models.groq import GroqModel

        model = _resolve_model("groq:llama-3")
        assert isinstance(model, GroqModel)

    def test_bare_model_defaults_to_openai(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        from pydantic_ai.models.openai import OpenAIChatModel

        model = _resolve_model("gpt-4o")
        assert isinstance(model, OpenAIChatModel)

    def test_ollama_uses_default_base_url(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        monkeypatch.delenv("UDSPY_LM_OPENAI_COMPATIBLE_BASE_URL", raising=False)
        from pydantic_ai.models.openai import OpenAIChatModel

        model = _resolve_model("ollama:llama2")
        assert isinstance(model, OpenAIChatModel)

    def test_never_mutates_os_environ(self, monkeypatch):
        monkeypatch.setenv("UDSPY_LM_API_KEY", "udspy-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        snapshot = dict(os.environ)
        _resolve_model("openai:gpt-4o")
        assert dict(os.environ) == snapshot
