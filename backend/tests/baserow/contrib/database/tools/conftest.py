import pytest
from pydantic_ai import Agent


@pytest.fixture(autouse=True)
def no_model_calls(monkeypatch):
    """
    The shared tools must never call a model, whichever client runs them. Calls
    are also checked after the test, in case the caller swallowed the error.
    """

    calls = []

    def fail(*args, **kwargs):
        calls.append(args)
        raise AssertionError("A shared tool called a model.")

    for method in ("run", "run_sync", "run_stream", "iter"):
        monkeypatch.setattr(Agent, method, fail)
    yield
    assert not calls, "A shared tool called a model."
