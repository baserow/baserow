import asyncio
from collections.abc import Awaitable, Callable
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, call

from django.utils.translation import gettext_lazy

import pytest
from asgiref.sync import async_to_sync
from loguru import logger
from pydantic_ai.messages import ModelMessagesTypeAdapter

from baserow.core.chat_runs.constants import ChatRunEventKind, ChatRunStopReason
from baserow.core.chat_runs.models import ChatRunStatus
from baserow_enterprise.assistant.assistant import BackgroundAssistant
from baserow_enterprise.assistant.history import NOT_STARTED_ANSWER
from baserow_enterprise.assistant.runs import NAVIGATION_EVENT
from baserow_enterprise.assistant.tools.navigation.utils import NAVIGATED
from baserow_enterprise.assistant.types import TableNavigationType

ORDERS_TABLE = TableNavigationType(
    type="database-table", database_id=1, table_id=2, table_name="Orders"
)


@pytest.mark.django_db
def test_tool_status_and_navigation_go_to_the_journal(
    background_assistant: BackgroundAssistant,
):
    helpers = background_assistant._tool_helpers
    journal = background_assistant._journal

    helpers.update_status(gettext_lazy("Listing tables..."))
    confirmation = helpers.navigate_to(ORDERS_TABLE)

    assert confirmation == NAVIGATED
    assert journal.emit.call_args_list == [
        call(ChatRunEventKind.PROGRESS, {"text": "Listing tables..."}),
        call(
            NAVIGATION_EVENT,
            {
                "location": {
                    "type": "database-table",
                    "database_id": 1,
                    "table_id": 2,
                    "table_name": "Orders",
                },
                "origin_tab_id": "tab-1",
            },
            flush_now=True,
        ),
    ]
    # A lazy translation would be resolved later, outside the run's language.
    assert type(journal.emit.call_args_list[0].args[1]["text"]) is str


@pytest.mark.django_db
def test_a_tool_that_ends_after_a_stop_does_not_navigate(
    background_assistant: BackgroundAssistant,
):
    background_assistant._tool_helpers.cancel()

    assert background_assistant._tool_helpers.navigate_to(ORDERS_TABLE) == NAVIGATED
    background_assistant._journal.emit.assert_not_called()


@pytest.mark.django_db
def test_a_run_closes_its_model_client(
    background_assistant: BackgroundAssistant, mocker
):
    model = background_assistant._model = MagicMock()
    mocker.patch.object(background_assistant, "_stream_answer")
    background_assistant._journal.wait_for_stop = AsyncMock(
        side_effect=asyncio.Event().wait
    )

    async_to_sync(background_assistant.answer)("Add rows", None, False)

    model.__aenter__.assert_awaited_once()
    model.__aexit__.assert_awaited_once()


@pytest.mark.django_db
def test_a_prompt_stopped_before_reaching_the_model_records_that_nothing_changed(
    background_assistant: BackgroundAssistant, mocker
):
    async def never_answer(*args) -> None:
        await asyncio.Event().wait()

    mocker.patch.object(background_assistant, "_produce", never_answer)
    journal = background_assistant._journal
    journal.stop_reason = ChatRunStopReason.CANCELLED
    journal.wait_for_stop = AsyncMock(return_value=ChatRunStopReason.CANCELLED)

    outcome = async_to_sync(background_assistant.answer)("Add rows", None, False)

    history = ModelMessagesTypeAdapter.validate_json(outcome.result.message_history)
    assert outcome.status == ChatRunStatus.CANCELLED
    assert [part.content for message in history for part in message.parts] == [
        "Add rows",
        NOT_STARTED_ANSWER,
    ]


async def _fail_agent(
    assistant: BackgroundAssistant, prompt: str, failure: Exception
) -> None:
    assistant._stream_agent_run = AsyncMock(side_effect=failure)
    await assistant._run_agent(prompt, None, asyncio.Queue())


async def _fail_answer(
    assistant: BackgroundAssistant, prompt: str, failure: Exception
) -> None:
    assistant._produce = AsyncMock(side_effect=failure)
    assistant._journal.wait_for_stop = AsyncMock(side_effect=asyncio.Event().wait)
    await assistant.answer(prompt, None, False)


async def _fail_title(
    assistant: BackgroundAssistant, prompt: str, failure: Exception
) -> None:
    assistant._generate_chat_title = AsyncMock(side_effect=failure)
    await assistant._report_title(prompt)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "fail", [_fail_agent, _fail_answer, _fail_title], ids=["agent", "answer", "title"]
)
def test_failure_logs_exclude_private_inputs_and_provider_errors(
    background_assistant: BackgroundAssistant,
    fail: Callable[[BackgroundAssistant, str, Exception], Awaitable[None]],
):
    private_input = "private-chat-input-canary"
    failure = RuntimeError("private-provider-error-canary")

    output = StringIO()
    sink = logger.add(output, format="{message}", diagnose=True, backtrace=True)
    try:
        async_to_sync(fail)(background_assistant, private_input, failure)
    finally:
        logger.remove(sink)

    logged = output.getvalue()
    assert "RuntimeError" in logged
    assert str(background_assistant._chat.id) in logged
    assert private_input not in logged
    assert str(failure) not in logged
