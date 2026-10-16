import asyncio
import time
from typing import Any

import pytest
from asgiref.sync import async_to_sync
from pydantic_ai.models.function import DeltaToolCall, FunctionModel

from baserow.contrib.database.models import Database
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRunStatus
from baserow.core.chat_runs.tasks import execute_chat_run
from baserow_enterprise.assistant.assistant import BackgroundAssistant
from baserow_enterprise.assistant.retrying_model import RetryingModel


async def _create_a_database(messages, info):
    if len(messages) > 1:
        yield "Created."
        return
    yield {
        0: DeltaToolCall(
            name="create_builders",
            json_args=(
                '{"builders": [{"name": "Kuma DB", "type": "database"}], '
                '"thought": "Create it"}'
            ),
            tool_call_id="call-1",
        )
    }


@pytest.mark.django_db(transaction=True)
def test_a_stopped_run_finishes_only_after_its_running_tool_ends(
    assistant_run, kuma_model, mocker, fast_journal
):
    run = assistant_run(content="Create a database")
    order: list[str] = []

    def stop_while_listing(user, workspace) -> list:
        ChatRunHandler().request_cancel(run.id)
        time.sleep(0.5)
        order.append("tool finished")
        return []

    mocker.patch(
        "baserow_enterprise.assistant.tools.core.helpers.list_builder_items",
        side_effect=stop_while_listing,
    )
    finish_run = ChatRunHandler.finish_run

    def record_finish(handler: ChatRunHandler, *args: Any, **kwargs: Any) -> bool:
        order.append("run finished")
        return finish_run(handler, *args, **kwargs)

    mocker.patch.object(ChatRunHandler, "finish_run", record_finish)
    kuma_model(_create_a_database)

    execute_chat_run(str(run.id))

    run.refresh_from_db()
    assert run.status == ChatRunStatus.CANCELLED
    assert order == ["tool finished", "run finished"]
    assert not Database.objects.filter(name="Kuma DB").exists()


@pytest.mark.django_db
def test_a_cancelled_run_starts_no_new_model_request(
    background_assistant: BackgroundAssistant,
):
    requests = []

    async def stream(messages, info):
        requests.append(messages)
        background_assistant._tool_helpers.cancel()
        # A printed tool call fails the final-answer check, so the agent asks again.
        yield '{"name": "create_rows", "arguments": {"rows": []}}'

    background_assistant._model = RetryingModel(FunctionModel(stream_function=stream))
    with pytest.raises(asyncio.CancelledError):
        async_to_sync(background_assistant._stream_agent_run)(
            "Add rows", None, asyncio.Queue()
        )

    assert len(requests) == 1
