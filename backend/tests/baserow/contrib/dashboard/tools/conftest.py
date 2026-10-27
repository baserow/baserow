import pytest
from pydantic_ai import Agent

from baserow.core.tools import ToolContext


@pytest.fixture(autouse=True)
def no_model_calls(monkeypatch):
    """The shared tools must never call a model, whichever client runs them."""

    calls = []

    def fail(*args, **kwargs):
        calls.append(args)
        raise AssertionError("A shared tool called a model.")

    for method in ("run", "run_sync", "run_stream", "iter"):
        monkeypatch.setattr(Agent, method, fail)
    yield
    assert not calls, "A shared tool called a model."


@pytest.fixture
def dashboard_ctx(data_fixture):
    """A user's workspace with a dashboard."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(
        workspace=workspace, name="Sales"
    )
    return ToolContext(user=user, workspace=workspace), dashboard
