from collections.abc import Mapping
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from anthropic import (
    APIRequest,
    APIResponse,
    AsyncAPIResponse,
    AsyncCallNext,
    CallNext,
    Middleware,
)
from pydantic_ai.providers.anthropic import AnthropicProvider


def get_retry_after(headers: Mapping[str, str]) -> float | None:
    """Read Anthropic's millisecond, second, or HTTP-date retry header.

    :param headers: Provider response headers with lowercase names.
    :return: Requested delay in seconds, or None for an absent/invalid header.
    """

    for name, divisor in (("retry-after-ms", 1000), ("retry-after", 1)):
        try:
            return float(headers[name]) / divisor
        except (KeyError, TypeError, ValueError):
            pass
    try:
        retry_at = parsedate_to_datetime(headers["retry-after"])
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return (retry_at - datetime.now(timezone.utc)).total_seconds()
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


class BoundedAnthropicRetryMiddleware(Middleware):
    """Keep short SDK retries, but surface errors asking for a longer wait.

    HTTP timeouts exclude retry sleeps. Before Anthropic 1.0 the SDK only
    honored Retry-After values up to 60 seconds; keep that maximum, without
    retrying earlier than the server asks us to.
    """

    @staticmethod
    def _limit_retries(response: APIResponse[Any] | AsyncAPIResponse[Any]) -> None:
        retry_after = get_retry_after(response.headers)
        if retry_after is not None and retry_after > 60:
            response.headers["x-should-retry"] = "false"

    def handle(self, request: APIRequest, call_next: CallNext) -> APIResponse[Any]:
        response = call_next(request)
        self._limit_retries(response)
        return response

    async def handle_async(
        self, request: APIRequest, call_next: AsyncCallNext
    ) -> AsyncAPIResponse[Any]:
        response = await call_next(request)
        self._limit_retries(response)
        return response


class BoundedAnthropicProvider(AnthropicProvider):
    """An Anthropic provider owning its HTTP client and limiting retry waits."""

    def __init__(self, *, api_key: str | None = None) -> None:
        super().__init__(api_key=api_key)
        # The SDK's public copy API retains the HTTP client owned by this
        # provider, including its close/reopen lifecycle across model scopes.
        self._client = self.client.with_middleware(BoundedAnthropicRetryMiddleware())
