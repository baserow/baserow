import pytest
from pydantic_ai import Agent

from baserow_enterprise_tests.builder.tools.fixtures import block_model_calls


def test_a_model_call_fails_even_when_the_caller_swallows_it():
    monkeypatch = pytest.MonkeyPatch()
    blocker = block_model_calls(monkeypatch)
    next(blocker)
    try:
        with pytest.raises(AssertionError, match="called a model"):
            Agent.run_sync(None, "hello")
        with pytest.raises(AssertionError, match="called a model"):
            next(blocker)
    finally:
        monkeypatch.undo()


def test_the_agent_is_restored_after_each_test():
    monkeypatch = pytest.MonkeyPatch()
    before = {m: Agent.__dict__.get(m) for m in ("run", "run_sync", "iter")}
    blocker = block_model_calls(monkeypatch)
    next(blocker)
    monkeypatch.undo()

    assert {m: Agent.__dict__.get(m) for m in before} == before
