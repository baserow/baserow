"""
A pydantic-ai Model wrapper that retries on transient provider errors.

Provider SDKs (Groq, Anthropic, OpenAI) sometimes raise exceptions that
are transient — e.g. ``groq.APIError: Failed to parse tool call arguments
as JSON``.  ``RetryingModel`` wraps any pydantic-ai ``Model`` and adds retry
logic around ``request()`` with configurable back-off.

Tool calls that Groq rejects
----------------------------
Groq rejects a tool call it cannot parse with a ``tool_use_failed`` error
whose ``failed_generation`` holds the text the model wrote.  pydantic-ai
2.50 handles this error itself: a ``failed_generation`` that parses into a
name and arguments becomes a ``ToolCallPart``, and one that does not parse
is returned as text.  ``request()`` returns that text as a ``TextPart`` with
``finish_reason='error'``.  A stream emits it as text deltas; there the
error usually comes with an empty ``failed_generation`` because the text
has already streamed.  Kuma recovers each case as follows:

- ``request()``: ``_recover_printed_tool_call`` repairs the text into a call
  to one of the request's tools.
- Streams: text that has streamed cannot become a tool call any more.  It
  reaches the final-answer validator
  (``output_validation.validate_final_answer``), whose retry message gives
  the model the corrected call (``thought`` moved to the top level) when it
  names one of the run's tools and is short.
- A ``tool_use_failed`` body that pydantic-ai does not recognize is raised,
  and so is any ``tool_use_failed`` at stream setup.
  ``_try_recover_tool_use_failed`` turns it into a ``ToolCallPart`` in
  ``request()``, in ``request_stream()`` setup, and in
  ``_ErrorRecoveringStream`` while the stream is consumed.  That last error
  occurs after the ``yield``, where ``@asynccontextmanager`` cannot yield a
  replacement, so the wrapper emits the recovered part as stream events.

For other retryable errors during ``request_stream`` setup, we fall back to
the retrying ``request()`` method and wrap the result in
``_PreFetchedResponse``.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from anthropic import APIConnectionError, APIStatusError, AsyncAnthropic
from loguru import logger
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
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

from baserow.core.generative_ai.anthropic import get_retry_after

# Transient Groq errors that are safe to retry.
_RETRYABLE_MESSAGES = frozenset(
    {
        "Failed to parse tool call arguments as JSON",
        "Tool call validation failed",
    }
)


def _is_transient_provider_error(exc: Exception) -> bool:
    """Return True for provider errors that are transient and safe to retry."""

    if isinstance(exc, ModelHTTPError) and exc.status_code == 429:
        return True
    # Anthropic SDK retries are disabled when this wrapper owns the budget.
    # Preserve its connection, timeout, conflict, and server-error retries.
    provider_error = exc.__cause__ if isinstance(exc, ModelAPIError) else exc
    if isinstance(provider_error, APIConnectionError):
        return True
    if isinstance(provider_error, APIStatusError):
        return provider_error.status_code in (408, 409, 429) or (
            provider_error.status_code >= 500
        )
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


_OPENER_CLOSERS = {"{": "}", "[": "]"}
_CLOSERS = frozenset(_OPENER_CLOSERS.values())


def _fix_closing_brackets(text: str) -> str:
    """
    Drop each ``"`` that sits between two closing brackets and, when the text
    ends with such a quote and a closing bracket, append the closing bracket
    that is missing if exactly one is.

    That ending, with one bracket missing, is how gpt-oss ends a call it prints
    (``}"}``). Any other missing bracket means the call was cut off, so it stays
    missing and the text does not parse. Only characters outside of strings
    count, so a string keeps its content.

    :param text: JSON text that does not parse.
    :return: The text with the repairs applied.
    """

    kept: list[str] = []
    missing: list[str] = []
    in_string = escaped = False
    last_dropped_quote_index: int | None = None
    for index, char in enumerate(text):
        if in_string:
            if char == '"' and not escaped:
                in_string = False
            escaped = char == "\\" and not escaped
        elif char == '"':
            if (
                text[index - 1 : index] in _CLOSERS
                and text[index + 1 : index + 2] in _CLOSERS
            ):
                last_dropped_quote_index = index
                continue
            in_string = True
        elif char in _OPENER_CLOSERS:
            missing.append(_OPENER_CLOSERS[char])
        elif char in _CLOSERS and missing:
            missing.pop()
        kept.append(char)
    ends_with_dropped_quote = last_dropped_quote_index == len(text.rstrip()) - 2
    closer = missing[0] if len(missing) == 1 and ends_with_dropped_quote else ""
    return "".join(kept) + closer


def repair_printed_tool_call(text: str) -> tuple[str, dict[str, Any]] | None:
    """
    Read a tool call that a model printed as JSON text, such as Groq's
    ``failed_generation``.

    Text that does not parse gets two repairs, and nothing else: a ``"`` between
    two closing brackets is dropped, and a text that ends with one (``}"}``) and
    misses exactly one closing bracket gets it appended.

    :param text: The printed tool call.
    :return: The tool name and its arguments, or None when the text is not an
        object with exactly a string ``name`` and an object ``arguments``.
    """

    try:
        call = json.loads(text)
    except (ValueError, RecursionError):
        try:
            call = json.loads(_fix_closing_brackets(text))
        except (ValueError, RecursionError):
            return None
    if (
        isinstance(call, dict)
        and call.keys() == {"name", "arguments"}
        and isinstance(call["name"], str)
        and isinstance(call["arguments"], dict)
    ):
        return call["name"], call["arguments"]
    return None


def _recover_failed_generation(failed_gen: str, model_name: str = "") -> ModelResponse:
    """Turn a ``failed_generation`` string into a synthetic ``ModelResponse``.

    If the JSON is valid and holds ``name`` + ``arguments``, or JSON that does
    not parse is repaired by ``repair_printed_tool_call``, returns a
    ``ToolCallPart`` so pydantic-ai's validation loop can tell the model what
    was wrong.  For truly malformed JSON, extracts the tool name (best-effort)
    and returns a ``ToolCallPart`` with empty args so pydantic-ai's validation
    rejects it and sends a retry prompt.
    """

    try:
        parsed = json.loads(failed_gen)
    except (ValueError, RecursionError):
        tool_call = repair_printed_tool_call(failed_gen)
    else:
        is_call = isinstance(parsed, dict) and parsed.keys() >= {"name", "arguments"}
        tool_call = (parsed["name"], parsed["arguments"]) if is_call else None
    if tool_call is not None:
        tool_name, arguments = tool_call
        return ModelResponse(
            parts=[ToolCallPart(tool_name=tool_name, args=json.dumps(arguments))],
            model_name=model_name,
        )

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

    Works with both ``ModelHTTPError`` (non-streaming path and stream setup)
    and raw provider ``APIError`` (streaming path, when pydantic-ai does not
    recognize the error body).
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


def _recover_printed_tool_call(
    response: ModelResponse, model_request_parameters: ModelRequestParameters
) -> ModelResponse:
    """
    Turn a tool call that the provider rejected and returned as text back into a
    tool call.

    pydantic-ai returns a ``failed_generation`` it cannot parse as a text-only
    response with ``finish_reason="error"``.

    :param response: The response of the wrapped model.
    :param model_request_parameters: The request, whose function and output tools
        are the only tools a recovered call may name.
    :return: A copy of the response with the repaired tool call as its only part,
        or the response unchanged when its text is not a call to one of the tools.
    """

    if response.finish_reason != "error" or not all(
        isinstance(part, TextPart) for part in response.parts
    ):
        return response
    tool_call = repair_printed_tool_call(
        "".join(part.content for part in response.parts)
    )
    if tool_call is None or tool_call[0] not in model_request_parameters.tool_defs:
        return response
    tool_name, arguments = tool_call
    logger.info("[assistant] Recovered a tool call printed as text: {}", tool_name)
    return replace(response, parts=[ToolCallPart(tool_name=tool_name, args=arguments)])


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
    "google": {
        "api_key": "GOOGLE_API_KEY",
    },
    "google-gla": {
        "api_key": "GOOGLE_API_KEY",
    },
    "google-cloud": {
        "api_key": "GOOGLE_API_KEY",
    },
    "google-vertex": {
        "api_key": "GOOGLE_API_KEY",
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

    from baserow_enterprise.assistant.model_profiles import get_model_class

    model_class = get_model_class(f"groq:{name}", GroqModel)
    return model_class(name, provider=GroqProvider(api_key=creds["api_key"]))


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
    """Build a Google model with a provider-owned HTTP client.

    Pydantic AI creates a fresh client with its safe 600-second timeout and keeps
    ownership so the client can be closed with the provider.
    """

    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    return GoogleModel(
        name,
        provider=GoogleProvider(api_key=creds["api_key"]),
    )


def _make_google_vertex(name: str, creds: dict[str, str | None]) -> Model:
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google_cloud import GoogleCloudProvider

    return GoogleModel(
        name,
        provider=GoogleCloudProvider(api_key=creds["api_key"]),
    )


_PROVIDER_FACTORIES: dict[str, Callable[[str, dict[str, str | None]], Model]] = {
    "openai": _make_openai,
    "groq": _make_groq,
    "anthropic": _make_anthropic,
    "ollama": _make_ollama,
    # Both spellings resolve here; resolve_assistant_model() normalises them.
    "google-gla": _make_google,
    "google": _make_google,
    "google-vertex": _make_google_vertex,
    "google-cloud": _make_google_vertex,
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
        # Both string-resolved and database-backed models pass through here.
        # Otherwise the SDK can sleep for minutes inside each bounded attempt.
        if self._uses_anthropic(self._resolved):
            self._resolved.provider.client.max_retries = 0
        return self._resolved

    @wrapped.setter
    def wrapped(self, value: Model) -> None:
        self._resolved = value

    def _delay_for(self, attempt: int) -> float:
        """Exponential back-off delay capped at ``max_delay``."""
        return min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)

    @staticmethod
    def _uses_anthropic(model: Model) -> bool:
        provider = model.provider
        return provider is not None and isinstance(provider.client, AsyncAnthropic)

    def _retry_delay(self, exc: Exception, attempt: int) -> float | None:
        """Return a delay, or None if Anthropic asks to exceed the retry budget."""

        delay = self._delay_for(attempt)
        if self._uses_anthropic(self.wrapped):
            headers = None
            if isinstance(exc, ModelHTTPError):
                headers = exc.headers
            elif isinstance(exc, APIStatusError):
                headers = exc.response.headers
            if headers:
                retry_after = get_retry_after(headers)
                if headers.get("x-should-retry") == "false" or (
                    retry_after is not None and retry_after > self.max_delay
                ):
                    return None
                if retry_after is not None and retry_after > 0:
                    delay = retry_after
        elif isinstance(exc, ModelHTTPError) and exc.retry_after is not None:
            delay = min(exc.retry_after, self.max_delay)
        return delay

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """
        Send the request, retrying transient provider errors.

        :param messages: The conversation to send.
        :param model_settings: The settings for this request.
        :param model_request_parameters: The tools and output settings.
        :return: The response. A tool call that the provider rejected and returned
            as text comes back as a tool call when its JSON can be repaired.
        :raises Exception: The provider error when it is not transient, when the
            provider asks not to retry, or when all attempts failed.
        """

        wrapped = self.wrapped
        async with wrapped:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    response = await wrapped.request(
                        messages, model_settings, model_request_parameters
                    )
                except Exception as exc:
                    # Try to recover tool_use_failed into a response so
                    # pydantic-ai's validation loop can tell the model what
                    # was wrong (instead of blindly retrying the same request).
                    recovered = _try_recover_tool_use_failed(exc)
                    if recovered is not None:
                        logger.info(
                            "[assistant] Recovered tool_use_failed error into "
                            "ModelResponse"
                        )
                        return recovered

                    if (
                        not _is_transient_provider_error(exc)
                        or attempt == self.max_attempts
                    ):
                        raise
                    delay = self._retry_delay(exc, attempt)
                    if delay is None:
                        raise
                    logger.warning(
                        "[assistant] Model request failed (attempt {}/{}), "
                        "retrying in {:.1f}s: {}",
                        attempt,
                        self.max_attempts,
                        delay,
                        repr(exc),
                    )
                    await asyncio.sleep(delay)
                else:
                    return _recover_printed_tool_call(
                        response, model_request_parameters
                    )
        raise RuntimeError("Exhausted retries")  # pragma: no cover

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
        run_context: RunContext[Any] | None = None,
    ) -> AsyncIterator[StreamedResponse]:
        wrapped = self.wrapped
        async with wrapped:
            yielded = False
            try:
                async with wrapped.request_stream(
                    messages, model_settings, model_request_parameters, run_context
                ) as stream:
                    yielded = True
                    # Recovers tool_use_failed bodies pydantic-ai raises mid-stream.
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
                if self._uses_anthropic(wrapped):
                    delay = self._retry_delay(exc, 1)
                    if delay is None:
                        raise
                    await asyncio.sleep(delay)
                # Stream failed with a retryable error. Fall back to a
                # non-streaming request, whose nested model context is safe
                # because providers reference-count re-entrant scopes.
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

    pydantic-ai's ``GroqStreamedResponse`` handles a ``tool_use_failed`` error
    whose body it recognizes and re-raises any other.  This wrapper catches
    that re-raised ``APIError`` and emits a ``ToolCallPart`` so pydantic-ai's
    validation loop can tell the model what was wrong.
    """

    # Class attributes on StreamedResponse (dataclass fields with class-level
    # defaults such as ``final_result_event = None``, and the
    # ``_parts_manager`` cached_property) shadow ``__getattr__`` because
    # Python resolves class attributes before calling __getattr__ — the proxy
    # would silently use its own state instead of the inner stream's (e.g.
    # ``get()`` would build the response from an empty parts manager).  We
    # override them as properties so reads delegate to ``_inner``; writes
    # already delegate through ``__setattr__``.
    final_result_event = property(lambda self: self._inner.final_result_event)  # type: ignore[assignment]
    provider_response_id = property(lambda self: self._inner.provider_response_id)  # type: ignore[assignment]
    provider_details = property(lambda self: self._inner.provider_details)  # type: ignore[assignment]
    finish_reason = property(lambda self: self._inner.finish_reason)  # type: ignore[assignment]
    state = property(lambda self: self._inner.state)  # type: ignore[assignment]
    metadata = property(lambda self: self._inner.metadata)  # type: ignore[assignment]
    _cancelled = property(lambda self: self._inner._cancelled)  # type: ignore[assignment]
    _finished = property(lambda self: self._inner._finished)  # type: ignore[assignment]
    _parts_manager = property(lambda self: self._inner._parts_manager)  # type: ignore[assignment]

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

    async def close_stream(self) -> None:
        # Not delegating leaves the base class's NotImplementedError in place.
        await self._inner.close_stream()

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
