import asyncio
from typing import Any

from asgiref.sync import async_to_sync
from pydantic_ai import Agent

from baserow.core.ai_provider.constants import AI_PROVIDER_TEST_TIMEOUT_SECONDS


class ModelToolCallingNotSupportedError(Exception):
    def __init__(self, message: str, *, text_response_received: bool = False):
        self.text_response_received = text_response_received
        super().__init__(message)


class ModelTextResponseNotSupportedError(Exception):
    def __init__(self, message: str, *, tool_called: bool = False):
        self.tool_called = tool_called
        super().__init__(message)


def test_model_text_and_tool_calling(
    model: Any,
    *,
    max_tokens: int,
    timeout_seconds: float = AI_PROVIDER_TEST_TIMEOUT_SECONDS,
) -> None:
    """Make a time-bounded live request which must call a tool and return text.

    :param model: The pydantic-ai model to probe.
    :param max_tokens: The token ceiling of the probe request.
    :param timeout_seconds: The wall-clock budget for the whole probe.
    :return: None.
    :raises ModelToolCallingNotSupportedError: If the model declines or fails to call
        the test tool.
    :raises ModelTextResponseNotSupportedError: If the model returns no text output.
    :raises TimeoutError: If the probe exceeds ``timeout_seconds``.
    """

    async def run_test() -> None:
        async with asyncio.timeout(timeout_seconds):
            async with model:
                if model.profile.get("supports_tools", True) is False:
                    raise ModelToolCallingNotSupportedError(
                        "The model reports that it does not support tool calling."
                    )

                tool_called = False

                def baserow_model_compatibility_test(value: str) -> str:
                    """Return a successful result for the compatibility test."""

                    nonlocal tool_called
                    tool_called = True
                    return f"The compatibility test tool received {value}."

                agent = Agent(
                    model=model,
                    output_type=str,
                    tools=[baserow_model_compatibility_test],
                    instructions=(
                        "This is a model compatibility test. You must call the "
                        "`baserow_model_compatibility_test` tool exactly once. After "
                        "the tool returns, respond with the text `OK`."
                    ),
                    name="baserow_model_compatibility_test_agent",
                )
                result = await agent.run(
                    "Run the compatibility test now.",
                    model_settings={
                        "max_tokens": max_tokens,
                        "timeout": timeout_seconds,
                    },
                )
                if not isinstance(result.output, str) or not result.output.strip():
                    raise ModelTextResponseNotSupportedError(
                        "The model did not return a text response.",
                        tool_called=tool_called,
                    )
                if not tool_called:
                    raise ModelToolCallingNotSupportedError(
                        "The model did not call the compatibility test tool.",
                        text_response_received=True,
                    )

    try:
        async_to_sync(run_test)()
    except TimeoutError as exc:
        raise TimeoutError(
            f"The model compatibility test timed out after {timeout_seconds:g} seconds."
        ) from exc
