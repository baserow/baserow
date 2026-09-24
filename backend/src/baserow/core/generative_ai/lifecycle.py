from typing import Any

from asgiref.sync import async_to_sync


async def run_agent_with_model(
    agent: Any,
    prompt: Any,
    *,
    model: Any,
    **run_kwargs: Any,
) -> Any:
    """Run an agent while deterministically owning the model client lifecycle."""

    async with model:
        return await agent.run(prompt, model=model, **run_kwargs)


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
