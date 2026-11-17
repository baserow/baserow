import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.providers.openai import OpenAIProvider

from baserow_enterprise.assistant.chatgpt_plan import ChatGPTPlanResponsesModel


def _streamed_reply(text: str) -> httpx.Response:
    message = {
        "type": "message",
        "id": "msg_1",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }
    response = {
        "id": "resp_1",
        "object": "response",
        "created_at": 0,
        "model": "gpt-test",
        "status": "completed",
        "output": [message],
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
    }
    loc = {"item_id": "msg_1", "output_index": 0, "content_index": 0}
    events = [
        {"type": "response.created", "response": {**response, "output": []}},
        {"type": "response.output_item.added", "output_index": 0, "item": message},
        {"type": "response.output_text.delta", **loc, "delta": text, "logprobs": []},
        {"type": "response.output_item.done", "output_index": 0, "item": message},
        {"type": "response.completed", "response": response},
    ]
    body = "".join(
        f"event: {e['type']}\ndata: {json.dumps({**e, 'sequence_number': n})}\n\n"
        for n, e in enumerate(events)
    )
    return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})


@pytest.mark.asyncio
async def test_chatgpt_plan_model_sends_only_accepted_request_fields():
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return _streamed_reply("Hello")

    client = AsyncOpenAI(
        api_key="token",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    model = ChatGPTPlanResponsesModel(
        "gpt-test", provider=OpenAIProvider(openai_client=client)
    )
    agent = Agent(model, instructions="You are Kuma.")

    # Kuma's title agent uses a plain run() with these settings.
    result = await agent.run(
        "Hi", model_settings={"temperature": 0.7, "max_tokens": 100, "timeout": 15}
    )

    assert result.output == "Hello"
    body = bodies[0]
    assert body["stream"] is True
    assert body["store"] is False
    assert "temperature" not in body
    assert "max_output_tokens" not in body
    assert body["instructions"] == "You are Kuma."
    assert all(item.get("role") != "system" for item in body["input"])
