import asyncio
import threading
from unittest.mock import MagicMock

from django.db import DEFAULT_DB_ALIAS
from django.utils import translation

import pytest
from asgiref.sync import async_to_sync, sync_to_async
from pydantic_ai.messages import ModelResponse, TextPart

from baserow.config.db_routers import get_db_alias
from baserow.core.action.models import Action
from baserow.core.actions import CreateApplicationActionType
from baserow.core.chat_runs import runner as runner_module
from baserow.core.chat_runs.constants import (
    ChatRunErrorCode,
    ChatRunEventKind,
    ChatRunStopReason,
)
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.journal import ChatRunJournal
from baserow.core.chat_runs.models import ChatRun, ChatRunStatus
from baserow.core.chat_runs.tasks import execute_chat_run
from baserow.core.chat_runs.types import ChatRunOutcome
from baserow_enterprise.assistant.chat_run_type import AssistantChatRunType
from baserow_enterprise.assistant.exceptions import AssistantModelNotSupportedError
from baserow_enterprise.assistant.history import unfinished_answer
from baserow_enterprise.assistant.models import AssistantChat
from baserow_enterprise.assistant.runs import CHAT_TITLE_EVENT, ERROR_MODEL_UNAVAILABLE
from baserow_enterprise.assistant.telemetry import AssistantTraceOutcome
from baserow_enterprise.assistant.tools.core import helpers as core_helpers
from baserow_enterprise_tests.assistant.runs.utils import (
    ai_message,
    create_a_database,
    history_texts,
    traces,
)


async def _cancel(run: ChatRun, journal: ChatRunJournal) -> None:
    await sync_to_async(ChatRunHandler().request_cancel)(run.id)
    await asyncio.sleep(10)


async def _time_out(run: ChatRun, journal: ChatRunJournal) -> None:
    journal.request_stop(ChatRunStopReason.TIMEOUT)
    await asyncio.sleep(10)


async def _crash(run: ChatRun, journal: ChatRunJournal) -> None:
    await asyncio.sleep(0.05)
    raise RuntimeError("The provider went away")


@pytest.mark.django_db(transaction=True)
def test_a_run_streams_its_answer_and_saves_it_with_a_title(
    assistant_run, kuma_model, posthog_client, fast_journal, output_events
):
    async def stream(messages, info):
        yield "Hello"
        yield " world"

    def title(messages, info) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content="Greeting")])

    kuma_model(stream, function=title)
    run = assistant_run(content="Say hello", context={"generate_title": True})

    execute_chat_run(str(run.id))

    run.refresh_from_db()
    assert run.status == ChatRunStatus.COMPLETED
    assert run.outcome["content"] == "Hello world"
    kinds = [event["kind"] for event in output_events]
    assert kinds.index(CHAT_TITLE_EVENT) < kinds.index(ChatRunEventKind.RUN_FINISHED)
    assert output_events[-1]["data"]["message"]["content"] == "Hello world"
    assert AssistantChat.objects.get(id=run.chat_id).title == "Greeting"
    assert history_texts(run) == ["Say hello", "Hello world"]
    assert [trace["assistant_outcome"] for trace in traces(posthog_client)] == [
        AssistantTraceOutcome.ANSWERED
    ]


@pytest.mark.parametrize(
    "interrupt, status, error_code, trace_outcome",
    [
        (_cancel, "cancelled", "", AssistantTraceOutcome.CANCELLED),
        (
            _time_out,
            "failed",
            ChatRunErrorCode.TIMEOUT,
            AssistantTraceOutcome.INTERRUPTED,
        ),
        (_crash, "failed", ChatRunErrorCode.FAILED, AssistantTraceOutcome.ERROR),
    ],
    ids=["stop", "deadline", "model_error"],
)
@pytest.mark.django_db(transaction=True)
def test_an_unfinished_run_keeps_what_the_user_saw_and_closes_the_turn(
    assistant_run,
    kuma_model,
    posthog_client,
    fast_journal,
    mocker,
    interrupt,
    status,
    error_code,
    trace_outcome,
):
    journal = mocker.spy(runner_module, "ChatRunJournal")
    run = assistant_run(content="Add rows")

    async def stream(messages, info):
        yield "Adding rows"
        await interrupt(run, journal.spy_return)
        yield " never"

    kuma_model(stream)

    execute_chat_run(str(run.id))

    run.refresh_from_db()
    message = ai_message(run)
    history = history_texts(run)
    assert (run.status, run.error_code) == (status, error_code)
    assert message.content == "Adding rows"
    assert message.artifacts["run"] == {"status": status, "error_code": error_code}
    assert (history[0], history[-1]) == ("Add rows", unfinished_answer("Adding rows"))
    assert [trace["assistant_outcome"] for trace in traces(posthog_client)] == [
        trace_outcome
    ]


@pytest.mark.django_db(transaction=True)
def test_a_run_without_a_usable_model_fails_before_the_agent_starts(
    assistant_run, mocker
):
    mocker.patch(
        "baserow_enterprise.assistant.chat_run_type.check_lm_ready_or_raise",
        side_effect=AssistantModelNotSupportedError("down"),
    )
    assistant = mocker.patch(
        "baserow_enterprise.assistant.chat_run_type.BackgroundAssistant"
    )

    outcome = async_to_sync(AssistantChatRunType().execute)(
        assistant_run(), MagicMock()
    )

    assert outcome == ChatRunOutcome(
        status=ChatRunStatus.FAILED, error_code=ERROR_MODEL_UNAVAILABLE
    )
    assistant.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_tools_run_with_the_context_of_the_sending_request(
    assistant_run, kuma_model, mocker, fast_journal
):
    run = assistant_run(content="Create a database")
    chat = AssistantChat.objects.select_related("user__profile").get(id=run.chat_id)
    chat.user.profile.language = "fr"
    chat.user.profile.save()
    main_thread = threading.get_ident()
    seen = []
    list_builder_items = core_helpers.list_builder_items

    def record_context(user, workspace):
        seen.append(
            {
                "in_tool_thread": threading.get_ident() != main_thread,
                "db_alias": get_db_alias(),
                "language": translation.get_language(),
                "timezone": user.profile.timezone,
                "web_socket_id": getattr(user, "web_socket_id", "unset"),
            }
        )
        return list_builder_items(user, workspace)

    mocker.patch.object(core_helpers, "list_builder_items", side_effect=record_context)
    kuma_model(create_a_database)

    execute_chat_run(str(run.id))

    assert seen == [
        {
            "in_tool_thread": True,
            "db_alias": DEFAULT_DB_ALIAS,
            "language": "fr",
            "timezone": "Europe/Rome",
            "web_socket_id": None,
        }
    ]
    action = Action.objects.get(type=CreateApplicationActionType.type)
    assert action.session == run.context["client_session_id"]
    assert str(action.action_group) == run.context["action_group_id"]
