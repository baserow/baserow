import asyncio

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

from baserow_enterprise.assistant.deps import bind_tool_helpers
from baserow_enterprise.assistant.retrying_model import RetryingModel

from .utils import create_fake_tool_helpers


@pytest.mark.asyncio
async def test_a_cancelled_run_starts_no_model_request_while_it_is_bound():
    tool_helpers = create_fake_tool_helpers()
    requests = []

    def respond(messages, info) -> ModelResponse:
        requests.append(messages)
        return ModelResponse(parts=[TextPart(content="Done")])

    model = RetryingModel(FunctionModel(respond))
    agent = Agent(output_type=str)

    with bind_tool_helpers(tool_helpers):
        await agent.run("First", model=model)
        tool_helpers.cancel()
        with pytest.raises(asyncio.CancelledError):
            await agent.run("Second", model=model)
    await agent.run("Outside the run", model=model)

    assert len(requests) == 2
