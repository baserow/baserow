import asyncio
from typing import Any

from asgiref.sync import async_to_sync


async def run_agent_with_model(
    agent: Any,
    prompt: Any,
    *,
    model: Any,
    timeout_seconds: float | None = None,
    **run_kwargs: Any,
) -> Any:
    """Run an agent with a managed model client and an optional overall deadline.

    :param timeout_seconds: Wall-clock budget including provider retries, or None.
    """

    async with model:
        deadline = asyncio.timeout(timeout_seconds)
        try:
            async with deadline:
                return await agent.run(prompt, model=model, **run_kwargs)
        except TimeoutError as exc:
            if deadline.expired():
                raise TimeoutError(
                    f"The AI request timed out after {timeout_seconds:g} seconds."
                ) from exc
            raise


def run_agent_sync_with_model(
    agent: Any,
    prompt: Any,
    *,
    model: Any,
    **run_kwargs: Any,
) -> Any:
    """Synchronous bridge for :func:`run_agent_with_model` using one event loop."""

    return async_to_sync(run_agent_with_model)(
        agent,
        prompt,
        model=model,
        **run_kwargs,
    )
