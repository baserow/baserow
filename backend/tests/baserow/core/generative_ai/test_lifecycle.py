import pytest

from baserow.core.generative_ai.lifecycle import (
    run_agent_sync_with_model,
    run_agent_with_model,
)


class LifecycleModel:
    def __init__(self):
        self.events = []

    async def __aenter__(self):
        self.events.append("enter")
        return self

    async def __aexit__(self, *args):
        self.events.append("exit")


class FakeAgent:
    def __init__(self, error=None):
        self.error = error

    async def run(self, prompt, *, model, **kwargs):
        model.events.append(("run", prompt, kwargs))
        if self.error is not None:
            raise self.error
        return "result"


@pytest.mark.asyncio
async def test_async_agent_run_closes_model_on_success_and_failure():
    success_model = LifecycleModel()
    assert (
        await run_agent_with_model(
            FakeAgent(), "prompt", model=success_model, model_settings={"x": 1}
        )
        == "result"
    )
    assert success_model.events == [
        "enter",
        ("run", "prompt", {"model_settings": {"x": 1}}),
        "exit",
    ]

    failed_model = LifecycleModel()
    with pytest.raises(RuntimeError, match="failed before request"):
        await run_agent_with_model(
            FakeAgent(RuntimeError("failed before request")),
            "prompt",
            model=failed_model,
        )
    assert failed_model.events == [
        "enter",
        ("run", "prompt", {}),
        "exit",
    ]


def test_sync_agent_run_uses_one_balanced_model_scope():
    model = LifecycleModel()

    assert run_agent_sync_with_model(FakeAgent(), "prompt", model=model) == "result"
    assert model.events == ["enter", ("run", "prompt", {}), "exit"]


def test_sync_agent_run_closes_model_when_agent_fails():
    model = LifecycleModel()

    with pytest.raises(RuntimeError, match="sync run failed"):
        run_agent_sync_with_model(
            FakeAgent(RuntimeError("sync run failed")),
            "prompt",
            model=model,
        )

    assert model.events == ["enter", ("run", "prompt", {}), "exit"]
