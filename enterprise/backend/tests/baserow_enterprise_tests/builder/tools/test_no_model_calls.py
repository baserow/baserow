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


def test_the_autouse_fixture_is_active_in_this_folder(no_model_calls):
    with pytest.raises(AssertionError, match="called a model"):
        Agent.run_sync(None, "hello")

    assert len(no_model_calls) == 1
    no_model_calls.clear()
