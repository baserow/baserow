import pytest
from pydantic_ai import Agent


def test_the_autouse_fixture_is_active_in_this_folder(no_model_calls_over_mcp):
    with pytest.raises(AssertionError, match="called a model"):
        Agent.run_sync(None, "hello")

    assert len(no_model_calls_over_mcp) == 1
    no_model_calls_over_mcp.clear()
