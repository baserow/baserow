import pytest


@pytest.fixture(autouse=True)
def enable_agent_builder(settings):
    settings.FEATURE_FLAGS = ["agent-builder"]
