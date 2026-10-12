import pytest


@pytest.fixture(autouse=True)
def enable_agent_application(settings):
    settings.FEATURE_FLAGS = ["agent-builder"]
