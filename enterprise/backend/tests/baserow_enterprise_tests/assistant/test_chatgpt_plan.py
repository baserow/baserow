import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.providers.openai import OpenAIProvider

from baserow_enterprise.assistant import chatgpt_plan
from baserow_enterprise.assistant.chatgpt_plan import (
    TOOL_NAMESPACE,
    ChatGPTPlanError,
    ChatGPTPlanResponsesModel,
    build_authorization,
    finish_authorization,
)


def _streamed_reply(response_id: str, item: dict) -> httpx.Response:
    """A Responses stream whose output is the single ``item``."""

    response = {
        "id": response_id,
        "object": "response",
        "created_at": 0,
        "model": "gpt-test",
        "status": "completed",
        "output": [item],
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
    }
    events = [
        {"type": "response.created", "response": {**response, "output": []}},
        {"type": "response.output_item.added", "output_index": 0, "item": item},
    ]
    if item["type"] == "message":
        events.append(
            {
                "type": "response.output_text.delta",
                "item_id": item["id"],
                "output_index": 0,
                "content_index": 0,
                "delta": item["content"][0]["text"],
                "logprobs": [],
            }
        )
    events += [
        {"type": "response.output_item.done", "output_index": 0, "item": item},
        {"type": "response.completed", "response": response},
    ]
    body = "".join(
        f"event: {e['type']}\ndata: {json.dumps({**e, 'sequence_number': n})}\n\n"
        for n, e in enumerate(events)
    )
    return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})


def _message(text: str) -> dict:
    return {
        "type": "message",
        "id": "msg_1",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }


def _model(handler) -> ChatGPTPlanResponsesModel:
    client = AsyncOpenAI(
        api_key="token",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    return ChatGPTPlanResponsesModel(
        "gpt-test", provider=OpenAIProvider(openai_client=client)
    )


@pytest.mark.asyncio
async def test_chatgpt_plan_model_sends_only_accepted_request_fields():
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return _streamed_reply("resp_1", _message("Hello"))

    agent = Agent(_model(handler), instructions="You are Kuma.")

    # Kuma's title agent uses a plain run() with these settings.
    result = await agent.run(
        "Hi",
        model_settings={
            "temperature": 0.7,
            "max_tokens": 100,
            "top_p": 0.9,
            "timeout": 15,
        },
    )

    assert result.output == "Hello"
    body = bodies[0]
    assert body["stream"] is True
    assert body["store"] is False
    for rejected in ("temperature", "max_output_tokens", "top_p", "user"):
        assert rejected not in body
    assert body["instructions"] == "You are Kuma."
    assert all(item.get("role") != "system" for item in body["input"])


@pytest.mark.asyncio
async def test_chatgpt_plan_model_namespaces_tools_and_replays_calls():
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        if len(bodies) == 1:
            return _streamed_reply(
                "resp_1",
                {
                    "type": "function_call",
                    "id": "fc_1",
                    "call_id": "call_1",
                    "name": "list_tables",
                    "namespace": TOOL_NAMESPACE,
                    "arguments": "{}",
                    "status": "completed",
                },
            )
        return _streamed_reply("resp_2", _message("You have 2 tables."))

    agent = Agent(_model(handler), instructions="You are Kuma.")

    @agent.tool_plain
    def list_tables() -> list[str]:
        """List the tables in the workspace."""

        return ["Projects", "Tasks"]

    result = await agent.run("Which tables do I have?")

    assert result.output == "You have 2 tables."
    first, second = bodies
    assert [tool["type"] for tool in first["tools"]] == ["namespace"]
    namespace = first["tools"][0]
    assert namespace["name"] == TOOL_NAMESPACE
    assert [tool["name"] for tool in namespace["tools"]] == ["list_tables"]

    # The follow-up request carries the call with its namespace and the result,
    # without item IDs that point at responses nothing stored.
    call = next(i for i in second["input"] if i.get("type") == "function_call")
    assert call["namespace"] == TOOL_NAMESPACE
    assert call["name"] == "list_tables"
    assert "id" not in call
    output = next(i for i in second["input"] if i.get("type") == "function_call_output")
    assert output["call_id"] == "call_1"
    assert second["store"] is False


def test_failed_code_exchange_keeps_the_issued_client_id(tmp_path, monkeypatch):
    credentials = tmp_path / "plan.json"
    monkeypatch.setenv("BASEROW_KUMA_CHATGPT_CREDENTIALS_FILE", str(credentials))

    def reject(data):
        raise ChatGPTPlanError("Token endpoint returned 400: invalid_grant")

    monkeypatch.setattr(chatgpt_plan, "_token_request", reject)

    url, pending = build_authorization(1455)
    assert "client_id=dynamic_agent_client" in url

    callback = (
        f"http://127.0.0.1:1455/auth/callback?code=abc&state={pending['state']}"
        "&client_id=oaiapp_issued"
    )
    with pytest.raises(ChatGPTPlanError):
        finish_authorization(callback, pending)

    retry_url, retry_pending = build_authorization(1455)
    assert "client_id=oaiapp_issued" in retry_url
    assert "agent_name_hint" not in retry_url
    assert retry_pending["client_id"] == "oaiapp_issued"
