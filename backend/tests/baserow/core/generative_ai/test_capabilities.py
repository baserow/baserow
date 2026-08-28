import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from baserow.core.generative_ai.capabilities import (
    ModelToolCallingNotSupportedError,
)
from baserow.core.generative_ai.capabilities import (
    test_model_text_and_tool_calling as check_model_text_and_tool_calling,
)


def test_model_without_tool_support_is_rejected_without_making_a_request():
    lifecycle = []

    class ModelWithoutTools:
        profile = {"supports_tools": False}

        async def __aenter__(self):
            lifecycle.append("enter")
            return self

        async def __aexit__(self, *args):
            lifecycle.append("exit")

    with (
        patch("baserow.core.generative_ai.capabilities.Agent") as agent,
        pytest.raises(
            ModelToolCallingNotSupportedError,
            match="does not support tool calling",
        ),
    ):
        check_model_text_and_tool_calling(ModelWithoutTools(), max_tokens=16)

    agent.assert_not_called()
    assert lifecycle == ["enter", "exit"]


def test_compatibility_probe_passes_timeout_to_the_model_request():
    captured = {}

    class Model:
        profile = {"supports_tools": True}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    class FakeAgent:
        def __init__(self, *args, tools, **kwargs):
            self.tool = tools[0]

        async def run(self, *args, **kwargs):
            captured.update(kwargs)
            self.tool("OK")
            return SimpleNamespace(output="OK")

    with patch("baserow.core.generative_ai.capabilities.Agent", FakeAgent):
        check_model_text_and_tool_calling(Model(), max_tokens=16, timeout_seconds=12)

    assert captured["model_settings"] == {"max_tokens": 16, "timeout": 12}


def test_compatibility_probe_times_out_and_closes_the_model():
    lifecycle = []

    class Model:
        profile = {"supports_tools": True}

        async def __aenter__(self):
            lifecycle.append("enter")
            return self

        async def __aexit__(self, *args):
            lifecycle.append("exit")

    class HangingAgent:
        def __init__(self, *args, **kwargs):
            pass

        async def run(self, *args, **kwargs):
            await asyncio.Event().wait()

    with (
        patch("baserow.core.generative_ai.capabilities.Agent", HangingAgent),
        pytest.raises(TimeoutError, match="timed out after 0.01 seconds"),
    ):
        check_model_text_and_tool_calling(Model(), max_tokens=16, timeout_seconds=0.01)

    assert lifecycle == ["enter", "exit"]
