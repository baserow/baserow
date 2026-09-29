from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import AsyncMock, patch

import anthropic
import httpx2
import pytest
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelRequest, UserPromptPart
from pydantic_ai.models import ModelRequestParameters

from baserow.core.generative_ai.generative_ai_model_types import (
    AnthropicGenerativeAIModelType,
)


def _rate_limit_headers():
    return [
        {"retry-after": "300"},
        {"retry-after-ms": "300000"},
        {
            "retry-after": format_datetime(
                datetime.now(timezone.utc) + timedelta(minutes=5), usegmt=True
            )
        },
    ]


@pytest.mark.parametrize("headers", _rate_limit_headers())
@pytest.mark.parametrize("operation", ["upload", "delete"])
def test_anthropic_file_requests_do_not_wait_for_long_retry_after(headers, operation):
    handler = AnthropicGenerativeAIModelType().file_handler
    response = httpx2.Response(
        429,
        headers=headers,
        json={
            "type": "error",
            "error": {"type": "rate_limit_error", "message": "Busy"},
        },
    )
    with (
        patch("httpx2.HTTPTransport.handle_request", return_value=response) as send,
        patch("time.sleep") as sleep,
        handler._get_sync_client(settings_override={"api_key": "test"}) as client,
        pytest.raises(anthropic.RateLimitError),
    ):
        if operation == "upload":
            client.beta.files.upload(file=("test.pdf", b"pdf"))
        else:
            client.beta.files.delete("file-test")

    assert send.call_count == 1
    sleep.assert_not_called()
    assert client.is_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("headers", _rate_limit_headers())
async def test_anthropic_model_does_not_wait_for_long_retry_after(headers):
    model = AnthropicGenerativeAIModelType().get_ai_model(
        "claude-sonnet-4-5", settings_override={"api_key": "test"}
    )
    response = httpx2.Response(
        429,
        headers=headers,
        json={
            "type": "error",
            "error": {"type": "rate_limit_error", "message": "Busy"},
        },
    )
    with (
        patch(
            "httpx2.AsyncHTTPTransport.handle_async_request",
            new_callable=AsyncMock,
            return_value=response,
        ) as send,
        patch("anthropic._base_client.anyio.sleep", new_callable=AsyncMock) as sleep,
    ):
        # Re-entering a previously closed model must retain the policy and close
        # the newly allocated HTTP client too.
        for _ in range(2):
            async with model:
                assert not model.provider.client.is_closed()
                with pytest.raises(ModelHTTPError) as error:
                    await model.request(
                        [ModelRequest(parts=[UserPromptPart("OK")])],
                        {"timeout": 0.01},
                        ModelRequestParameters(),
                    )
                assert error.value.status_code == 429
            assert model.provider.client.is_closed()

    assert send.await_count == 2
    sleep.assert_not_awaited()


@pytest.mark.parametrize("status", [408, 409, 429, 500, 503])
@pytest.mark.parametrize("retry_after", [None, "2", "60"])
def test_anthropic_files_keep_short_transient_retries(status, retry_after):
    headers = {"retry-after": retry_after} if retry_after else {}
    response = httpx2.Response(
        status,
        headers=headers,
        json={"type": "error", "error": {"type": "api_error", "message": "Busy"}},
    )
    handler = AnthropicGenerativeAIModelType().file_handler
    with (
        patch("httpx2.HTTPTransport.handle_request", return_value=response) as send,
        patch("time.sleep") as sleep,
        handler._get_sync_client(settings_override={"api_key": "test"}) as client,
        pytest.raises(anthropic.APIStatusError),
    ):
        client.beta.files.delete("file-test")

    assert send.call_count == 3
    assert sleep.call_count == 2
    assert all(0 < call.args[0] <= 60 for call in sleep.call_args_list)
    if retry_after:
        assert [call.args[0] for call in sleep.call_args_list] == [
            float(retry_after)
        ] * 2


def test_anthropic_files_keep_connection_retries():
    handler = AnthropicGenerativeAIModelType().file_handler
    with (
        patch(
            "httpx2.HTTPTransport.handle_request",
            side_effect=httpx2.ConnectError("Connection failed"),
        ) as send,
        patch("time.sleep") as sleep,
        handler._get_sync_client(settings_override={"api_key": "test"}) as client,
        pytest.raises(anthropic.APIConnectionError),
    ):
        client.beta.files.delete("file-test")

    assert send.call_count == 3
    assert sleep.call_count == 2
