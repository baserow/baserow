"""
A pydantic-ai Model wrapper that retries on transient provider errors.

Provider SDKs (Groq, Anthropic, OpenAI) sometimes raise exceptions that
are transient — e.g. ``groq.APIError: Failed to parse tool call arguments
as JSON``.  pydantic-ai handles *some* of these (e.g. ``tool_use_failed``
with a structured body), but others slip through.

``RetryingModel`` wraps any pydantic-ai ``Model`` and adds retry logic
around ``request()`` with configurable back-off.

Streaming recovery
------------------
pydantic-ai's ``GroqStreamedResponse`` catches ``APIError`` with
``tool_use_failed`` bodies, but only when the ``failed_generation`` JSON
is valid.  When Groq sends **truly malformed** JSON (not just
schema-invalid), pydantic-ai's ``Json[...]`` type fails to parse it and
re-raises the raw ``APIError``.

Since this error occurs *during* stream consumption (after yield),
``@asynccontextmanager`` cannot yield a replacement.  Instead we wrap
the stream in ``_ErrorRecoveringStream`` which intercepts ``APIError``
in its ``_get_event_iterator`` and emits a ``ToolCallPart`` (or
``TextPart``) so pydantic-ai's validation loop can tell the model
what was wrong.

For errors that occur *before* the stream is established (during
``request_stream`` setup), we fall back to the retrying ``request()``
method and wrap the result in ``_PreFetchedResponse``.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from pydantic_ai._run_context import RunContext
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models import (
    KnownModelName,
    Model,
    ModelRequestParameters,
    ModelResponseStreamEvent,
    StreamedResponse,
    infer_model,
)
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.settings import ModelSettings

# Transient Groq errors that are safe to retry.
_RETRYABLE_MESSAGES = frozenset(
    {
        "Failed to parse tool call arguments as JSON",
        "Tool call validation failed",
    }
)


def _is_transient_provider_error(exc: Exception) -> bool:
    """Return True for provider errors that are transient and safe to retry."""

    msg = str(exc)
    return any(needle in msg for needle in _RETRYABLE_MESSAGES)


def _extract_tool_use_failed(body: dict) -> dict | None:
    """Extract ``tool_use_failed`` error dict from an error body.

    Handles both wrapped (``{"error": {...}}``) and unwrapped layouts
    (the Groq SDK streaming path sets ``body=data["error"]``).
    """

    error = body.get("error", body)
    if not isinstance(error, dict):
        return None
    if error.get("code") != "tool_use_failed":
        return None
    return error


_TOOL_NAME_RE = re.compile(r'"name"\s*:\s*"([^"]+)"')


def _extract_tool_name(failed_gen: str) -> str:
    """Best-effort tool name extraction from truncated/malformed JSON."""

    m = _TOOL_NAME_RE.search(failed_gen)
    return m.group(1) if m else "unknown"


def _recover_failed_generation(failed_gen: str, model_name: str = "") -> ModelResponse:
    """Turn a ``failed_generation`` string into a synthetic ``ModelResponse``.

    If the JSON is valid and contains ``name`` + ``arguments``, returns a
    ``ToolCallPart`` so pydantic-ai's validation loop can tell the model
    what was wrong.  For truly malformed JSON, extracts the tool name
    (best-effort) and returns a ``ToolCallPart`` with empty args so
    pydantic-ai's validation rejects it and sends a retry prompt.
    """

    try:
        parsed = json.loads(failed_gen)
        if isinstance(parsed, dict) and "name" in parsed and "arguments" in parsed:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name=parsed["name"],
                        args=json.dumps(parsed["arguments"]),
                    )
                ],
                model_name=model_name,
            )
    except (json.JSONDecodeError, TypeError):
        pass

    # JSON is truly malformed (e.g. truncated).  We must NOT fall back to a
    # TextPart here because the stream may have already started emitting
    # tool-call events — mixing TextPart into a tool-call stream causes
    # pydantic-ai's AgentStream to fail with "unable to find output".
    #
    # Instead, try to extract the tool name from partial JSON and emit a
    # ToolCallPart with empty args.  pydantic-ai's validation will reject
    # the args and send a retry prompt to the model.
    tool_name = _extract_tool_name(failed_gen)
    return ModelResponse(
        parts=[
            ToolCallPart(
                tool_name=tool_name,
                args="{}",
            )
        ],
        model_name=model_name,
    )


def _try_recover_tool_use_failed(exc: Exception) -> ModelResponse | None:
    """Try to recover a ``tool_use_failed`` error into a ``ModelResponse``.

    Works with both ``ModelHTTPError`` (non-streaming path) and raw
    provider ``APIError`` (streaming path where pydantic-ai's handler
    couldn't parse the malformed JSON).
    """

    if isinstance(exc, ModelHTTPError):
        body = exc.body
        model_name = exc.model_name
    elif hasattr(exc, "body"):
        # Raw provider APIError (e.g. groq.APIError).
        body = exc.body  # type: ignore[union-attr]
        model_name = ""
    else:
        return None

    if not isinstance(body, dict):
        return None

    error = _extract_tool_use_failed(body)
    if error is None:
        return None

    failed_gen = error.get("failed_generation")
    if not failed_gen or not isinstance(failed_gen, str):
        return None

    return _recover_failed_generation(failed_gen, model_name)


# ---------------------------------------------------------------------------
# Provider credential resolution
# ---------------------------------------------------------------------------
# Maps provider prefixes to their native env-var names.
#
# Backward-compat: when a provider-specific var is not set we fall back to
# the deprecated UDSPY_LM_* vars so existing deployments keep working.
# This compat layer is intentionally minimal — new providers should NOT be
# added here; operators should use the standard env vars instead.

_PROVIDER_ENV: dict[str, dict[str, str | None]] = {
    "openai": {
        "api_key": "OPENAI_API_KEY",
        "base_url": "OPENAI_BASE_URL",
    },
    "groq": {
        "api_key": "GROQ_API_KEY",
    },
    "anthropic": {
        "api_key": "ANTHROPIC_API_KEY",
    },
    "ollama": {
        "base_url": "OLLAMA_BASE_URL",
    },
}


def _resolve_credentials(provider: str) -> dict[str, str | None]:
    """Return ``{"api_key": ..., "base_url": ...}`` for *provider*.

    Checks the provider-specific env var first, then falls back to the
    deprecated ``UDSPY_LM_API_KEY`` / ``UDSPY_LM_OPENAI_COMPATIBLE_BASE_URL``
    for backward-compat.  Never touches ``os.environ``.
    """

    env = _PROVIDER_ENV.get(provider, {})
    api_key_var = env.get("api_key")
    base_url_var = env.get("base_url")

    api_key = (
        (os.getenv(api_key_var) if api_key_var else None)
        or os.getenv("UDSPY_LM_API_KEY")
        or None
    )
    base_url = (
        (os.getenv(base_url_var) if base_url_var else None)
        or os.getenv("UDSPY_LM_OPENAI_COMPATIBLE_BASE_URL")
        or None
    )
    return {"api_key": api_key, "base_url": base_url}


# ---------------------------------------------------------------------------
# Per-provider model factories
# ---------------------------------------------------------------------------


def _make_openai(name: str, creds: dict[str, str | None]) -> Model:
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    kwargs = {k: v for k, v in creds.items() if v is not None}
    return OpenAIChatModel(name, provider=OpenAIProvider(**kwargs))


def _make_groq(name: str, creds: dict[str, str | None]) -> Model:
    from pydantic_ai.models.groq import GroqModel
    from pydantic_ai.providers.groq import GroqProvider

    return GroqModel(name, provider=GroqProvider(api_key=creds["api_key"]))


def _make_anthropic(name: str, creds: dict[str, str | None]) -> Model:
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider

    return AnthropicModel(name, provider=AnthropicProvider(api_key=creds["api_key"]))


def _make_ollama(name: str, creds: dict[str, str | None]) -> Model:
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.ollama import OllamaProvider

    base_url = creds["base_url"] or "http://localhost:11434/v1"
    return OpenAIChatModel(name, provider=OllamaProvider(base_url=base_url))


def _make_google(name: str, creds: dict[str, str | None]) -> Model:
    """Google models need a fresh httpx client per call to avoid event-loop
    binding issues in Django async views.
    See: https://github.com/pydantic/pydantic-ai/issues/3240
    """

    import httpx
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    return GoogleModel(
        name,
        provider=GoogleProvider(
            api_key=creds["api_key"], http_client=httpx.AsyncClient()
        ),
    )


def _make_google_vertex(name: str, creds: dict[str, str | None]) -> Model:
    import httpx
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    return GoogleModel(
        name,
        provider=GoogleProvider(
            api_key=creds["api_key"],
            http_client=httpx.AsyncClient(),
            vertexai=True,
        ),
    )


_PROVIDER_FACTORIES: dict[str, Callable[[str, dict[str, str | None]], Model]] = {
    "openai": _make_openai,
    "groq": _make_groq,
    "anthropic": _make_anthropic,
    "ollama": _make_ollama,
    "google-gla": _make_google,
    "google": _make_google,
    "google-vertex": _make_google_vertex,
}


# ---------------------------------------------------------------------------
# Model resolution
# ---------------------------------------------------------------------------


def _resolve_model(model_name: str) -> Model:
    """Resolve a model name to a pydantic-ai Model instance.

    Uses explicit provider construction with credential fallback to
    ``UDSPY_LM_API_KEY`` / ``UDSPY_LM_OPENAI_COMPATIBLE_BASE_URL``
    so we never need to set ``os.environ``.
    """

    provider = model_name.split(":")[0] if ":" in model_name else "openai"
    name = model_name.split(":", 1)[1] if ":" in model_name else model_name

    factory = _PROVIDER_FACTORIES.get(provider)
    if factory is not None:
        creds = _resolve_credentials(provider)
        return factory(name, creds)

    # Unknown provider — let pydantic-ai handle it.
    return infer_model(model_name)


class RetryingModel(WrapperModel):
    """Model wrapper that retries ``request()`` on transient provider errors.

    Model resolution is deferred until the first actual call so that
    constructing a ``RetryingModel`` from a model name string does not
    require provider API keys to be available at import/init time.

    Only ``request()`` has a retry loop.  ``request_stream()`` falls back
    to ``request()`` when the stream raises a retryable error, since
    ``@asynccontextmanager`` only allows a single ``yield``.
    """

    def __init__(
        self,
        wrapped: Model | KnownModelName,
        *,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
    ):
        # Bypass WrapperModel.__init__ to defer infer_model.
        Model.__init__(self)
        self._wrapped_or_name = wrapped
        self._resolved: Model | None = None
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay

    @property
    def wrapped(self) -> Model:
        if self._resolved is None:
            self._resolved = (
                self._wrapped_or_name
                if isinstance(self._wrapped_or_name, Model)
                else _resolve_model(self._wrapped_or_name)
            )
        return self._resolved

    @wrapped.setter
    def wrapped(self, value: Model) -> None:
        self._resolved = value

    def _delay_for(self, attempt: int) -> float:
        """Exponential back-off delay capped at ``max_delay``."""
        return min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        for attempt in range(1, self.max_attempts + 1):
            try:
                return await self.wrapped.request(
                    messages, model_settings, model_request_parameters
                )
            except Exception as exc:
                # Try to recover tool_use_failed into a response so
                # pydantic-ai's validation loop can tell the model what
                # was wrong (instead of blindly retrying the same request).
                recovered = _try_recover_tool_use_failed(exc)
                if recovered is not None:
                    logger.info(
                        "[assistant] Recovered tool_use_failed error into ModelResponse"
                    )
                    return recovered

                if (
                    not _is_transient_provider_error(exc)
                    or attempt == self.max_attempts
                ):
                    raise
                delay = self._delay_for(attempt)
                logger.warning(
                    "[assistant] Model request failed (attempt {}/{}), "
                    "retrying in {:.1f}s: {}",
                    attempt,
                    self.max_attempts,
                    delay,
                    repr(exc),
                )
                await asyncio.sleep(delay)
        raise RuntimeError("Exhausted retries")  # pragma: no cover

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
        run_context: RunContext[Any] | None = None,
    ) -> AsyncIterator[StreamedResponse]:
        yielded = False
        try:
            async with self.wrapped.request_stream(
                messages, model_settings, model_request_parameters, run_context
            ) as stream:
                yielded = True
                # Wrap the stream so that errors *during* chunk iteration
                # (e.g. groq.APIError with malformed failed_generation)
                # are caught and converted to recovery events rather than
                # crashing the entire agent run.
                yield _ErrorRecoveringStream(stream)
        except Exception as exc:
            if yielded:
                # Error during stream consumption that
                # _ErrorRecoveringStream couldn't handle.
                raise

            # Setup error — try to recover tool_use_failed.
            recovered = _try_recover_tool_use_failed(exc)
            if recovered is not None:
                logger.info(
                    "[assistant] Recovered tool_use_failed error "
                    "in stream into ModelResponse"
                )
                yield _PreFetchedResponse(recovered, model_request_parameters)
                return

            if not _is_transient_provider_error(exc):
                raise
            # Stream failed with a retryable error.  Fall back to a
            # non-streaming request which has its own retry loop.
            logger.warning(
                "[assistant] Stream failed with retryable error, "
                "falling back to non-streaming request: {}",
                repr(exc),
            )
            response = await self.request(
                messages, model_settings, model_request_parameters
            )
            yield _PreFetchedResponse(response, model_request_parameters)


class _ErrorRecoveringStream(StreamedResponse):
    """Transparent proxy around a ``StreamedResponse`` that catches provider
    errors during chunk iteration and converts ``tool_use_failed`` errors
    (even with malformed JSON) into recovery events.

    pydantic-ai's ``GroqStreamedResponse`` already handles ``tool_use_failed``
    when the ``failed_generation`` JSON is *valid*, but fails when it is
    truly malformed because ``Json[_GroqToolUseFailedGeneration]`` raises
    ``ValidationError``.  This wrapper catches the re-raised ``APIError``
    and emits a ``ToolCallPart`` or ``TextPart`` so pydantic-ai's
    validation loop can tell the model what was wrong.
    """

    # Dataclass fields on StreamedResponse that have class-level defaults
    # (e.g. ``final_result_event = None``).  These shadow ``__getattr__``
    # because Python finds the class attribute before calling __getattr__.
    # We override them as properties so reads delegate to ``_inner``.
    final_result_event = property(lambda self: self._inner.final_result_event)  # type: ignore[assignment]
    provider_response_id = property(lambda self: self._inner.provider_response_id)  # type: ignore[assignment]
    provider_details = property(lambda self: self._inner.provider_details)  # type: ignore[assignment]
    finish_reason = property(lambda self: self._inner.finish_reason)  # type: ignore[assignment]

    def __init__(self, inner: StreamedResponse):
        # Don't call super().__init__() — delegate everything to *inner*.
        # Only store our own _inner and _event_iterator on the instance.
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_event_iterator", None)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("_inner", "_event_iterator"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._inner, name, value)

    async def _get_event_iterator(
        self,
    ) -> AsyncIterator[ModelResponseStreamEvent]:
        try:
            async for event in self._inner._get_event_iterator():
                yield event
        except Exception as exc:
            recovered = _try_recover_tool_use_failed(exc)
            if recovered is None:
                raise
            logger.info(
                "[assistant] Recovered tool_use_failed error during stream consumption"
            )
            for i, part in enumerate(recovered.parts):
                yield self._parts_manager.handle_part(
                    vendor_part_id=f"recovered-{i}", part=part
                )

    # Abstract properties — delegate to inner stream.

    @property
    def model_name(self) -> str:
        return self._inner.model_name

    @property
    def provider_name(self) -> str | None:
        return self._inner.provider_name

    @property
    def provider_url(self) -> str | None:
        return self._inner.provider_url

    @property
    def timestamp(self) -> datetime:
        return self._inner.timestamp


class _PreFetchedResponse(StreamedResponse):
    """A ``StreamedResponse`` backed by an already-complete ``ModelResponse``.

    Used when ``request_stream`` falls back to ``request()`` after a
    retryable streaming error.  Emits all response parts as immediate
    ``PartStartEvent`` s so pydantic-ai can process them normally.
    """

    def __init__(
        self,
        response: ModelResponse,
        model_request_parameters: ModelRequestParameters,
    ):
        super().__init__(model_request_parameters=model_request_parameters)
        self._response = response
        self._usage.input_tokens = response.usage.input_tokens
        self._usage.output_tokens = response.usage.output_tokens

    async def _get_event_iterator(
        self,
    ) -> AsyncIterator[ModelResponseStreamEvent]:
        for i, part in enumerate(self._response.parts):
            yield self._parts_manager.handle_part(vendor_part_id=i, part=part)

    @property
    def model_name(self) -> str:
        return self._response.model_name or ""

    @property
    def provider_name(self) -> str | None:
        return self._response.provider_name

    @property
    def provider_url(self) -> str | None:
        return self._response.provider_url

    @property
    def timestamp(self) -> datetime:
        return self._response.timestamp or datetime.now(tz=timezone.utc)
