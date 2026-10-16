import asyncio
from io import StringIO
from unittest.mock import AsyncMock, call

from django.utils.translation import gettext_lazy

import pytest
from asgiref.sync import async_to_sync
from loguru import logger

from baserow.core.chat_runs.constants import PROGRESS
from baserow_enterprise.assistant.assistant import BackgroundAssistant
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
        call(PROGRESS, {"text": "Listing tables..."}),
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
@pytest.mark.parametrize("phase", ["agent", "background", "title"])
def test_failure_logs_exclude_private_inputs_and_provider_errors(
    background_assistant, mocker, phase
):
    private_input = "private-chat-input-canary"
    failure = RuntimeError("private-provider-error-canary")

    async def exercise():
        if phase == "agent":
            mocker.patch.object(
                background_assistant, "_stream_agent_run", side_effect=failure
            )
            await background_assistant._run_agent(private_input, None, asyncio.Queue())
        elif phase == "title":
            mocker.patch.object(
                background_assistant, "_generate_chat_title", side_effect=failure
            )
            await background_assistant._report_title(private_input)
        else:
            mocker.patch.object(background_assistant, "_produce", side_effect=failure)
            background_assistant._journal.wait_for_stop = AsyncMock(
                side_effect=asyncio.Event().wait
            )
            await background_assistant.answer(private_input, None, False)

    output = StringIO()
    sink = logger.add(output, format="{message}", diagnose=True, backtrace=True)
    try:
        async_to_sync(exercise)()
    finally:
        logger.remove(sink)

    logged = output.getvalue()
    assert "RuntimeError" in logged
    assert str(background_assistant._chat.id) in logged
    assert private_input not in logged
    assert str(failure) not in logged
