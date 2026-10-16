from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

import pytest
from pydantic_ai.messages import ModelMessagesTypeAdapter, ModelResponse, TextPart

from baserow.core.chat_runs.constants import (
    ERROR_INTERRUPTED,
    ERROR_MODEL_UNAVAILABLE,
    ERROR_NOT_STARTED,
    ERROR_TIMEOUT,
    TEXT_DELTA,
)
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRun, ChatRunStatus
from baserow.core.chat_runs.types import ChatRunOutcome
from baserow_enterprise.assistant.chat_run_type import (
    AssistantChatRunType,
    trace_outcome_for,
)
from baserow_enterprise.assistant.history import NOT_STARTED_ANSWER, unfinished_answer
from baserow_enterprise.assistant.models import AssistantChat
from baserow_enterprise.assistant.runs import AssistantRunResult
from baserow_enterprise.assistant.telemetry import AssistantTraceOutcome
from baserow_enterprise_tests.assistant.runs.fixtures import (
    ai_message,
    history_texts,
    traces,
)


def _chat(run: ChatRun) -> AssistantChat:
    return AssistantChat.objects.select_related("user", "workspace").get(id=run.chat_id)


@pytest.mark.parametrize(
    "status, error_code, outcome",
    [
        (ChatRunStatus.COMPLETED, "", AssistantTraceOutcome.ANSWERED),
        (ChatRunStatus.CANCELLED, "", AssistantTraceOutcome.CANCELLED),
        (ChatRunStatus.FAILED, ERROR_TIMEOUT, AssistantTraceOutcome.INTERRUPTED),
        (ChatRunStatus.CANCELLED, ERROR_INTERRUPTED, AssistantTraceOutcome.INTERRUPTED),
        (ChatRunStatus.FAILED, ERROR_NOT_STARTED, AssistantTraceOutcome.NOT_STARTED),
        (ChatRunStatus.FAILED, ERROR_MODEL_UNAVAILABLE, AssistantTraceOutcome.ERROR),
    ],
)
def test_trace_outcome_for_maps_how_a_run_ended(status, error_code, outcome):
    assert trace_outcome_for(status, error_code) == outcome


@pytest.mark.django_db
def test_only_the_chat_owner_can_access_a_run_while_a_member(
    assistant_run, enterprise_data_fixture
):
    run = assistant_run()
    owner = _chat(run).user
    member = enterprise_data_fixture.create_user()
    enterprise_data_fixture.create_user_workspace(
        user=member, workspace=run.workspace, permissions="MEMBER"
    )
    run_type = AssistantChatRunType()

    assert run_type.can_read(owner, run) is True
    assert run_type.can_cancel(owner, run) is True
    assert run_type.can_read(member, run) is False
    assert run_type.can_cancel(member, run) is False
    left_run = assistant_run()
    left_run.workspace.workspaceuser_set.all().delete()
    assert run_type.can_read(_chat(left_run).user, left_run) is False


@pytest.mark.django_db
def test_only_the_chat_owner_can_follow_it_while_a_member(
    assistant_run, enterprise_data_fixture, django_assert_num_queries
):
    chat = _chat(assistant_run())
    stranger = enterprise_data_fixture.create_user()
    run_type = AssistantChatRunType()

    with (
        patch(
            "baserow.config.db_routers.set_db_alias_for_read",
            return_value="lagging_replica",
        ),
        django_assert_num_queries(1),
    ):
        assert run_type.can_follow_chat(chat.user, chat.id) is True
    assert run_type.can_follow_chat(stranger, chat.id) is False
    assert run_type.can_follow_chat(AnonymousUser(), chat.id) is False
    chat.workspace.workspaceuser_set.filter(user=chat.user).delete()
    assert run_type.can_follow_chat(chat.user, chat.id) is False


@pytest.mark.django_db
def test_persist_outcome_saves_a_completed_answer(assistant_run, posthog_client):
    run = assistant_run()
    history = ModelMessagesTypeAdapter.dump_json(
        [ModelResponse(parts=[TextPart(content="Done")])]
    )
    result = AssistantRunResult(
        text="Done",
        message_history=history,
        sources=["https://baserow.io/docs"],
        trace_id="trace-1",
        title="New tables",
    )

    message = AssistantChatRunType().persist_outcome(
        run, ChatRunOutcome(status=ChatRunStatus.COMPLETED, result=result)
    )

    saved = ai_message(run)
    chat = _chat(run)
    assert (message["id"], message["content"], message["run_status"]) == (
        saved.id,
        "Done",
        None,
    )
    assert saved.artifacts == {"sources": ["https://baserow.io/docs"]}
    assert str(saved.action_group_id) == run.context["action_group_id"]
    assert saved.prediction.human_message_id == run.context["human_message_id"]
    assert saved.prediction.prediction == {
        "answer": "Done",
        "posthog_trace_id": "trace-1",
    }
    assert (bytes(chat.message_history), chat.title) == (history, "New tables")
    posthog_client.capture.assert_not_called()


@pytest.mark.django_db
def test_a_lost_run_saves_what_the_user_saw(
    assistant_run, posthog_client, django_capture_on_commit_callbacks, mocker
):
    run = assistant_run(content="Add rows")
    ChatRunHandler().claim_run(run.id)
    ChatRun.objects.filter(id=run.id).update(
        lease_expires_at=timezone.now() - timedelta(seconds=1)
    )
    mocker.patch(
        "baserow.core.chat_runs.handler.ChatRunHandler._recover_output",
        return_value=[
            {"kind": TEXT_DELTA, "data": {"segment": 0, "text": "Adding rows"}},
        ],
    )

    with django_capture_on_commit_callbacks(execute=True):
        ChatRunHandler().finalize_lost_runs()

    run.refresh_from_db()
    message = run.outcome
    assert message["id"] == ai_message(run).id
    assert (message["content"], message["run_status"], message["error_code"]) == (
        "Adding rows",
        "failed",
        ERROR_INTERRUPTED,
    )
    assert history_texts(run) == ["Add rows", unfinished_answer("Adding rows")]
    assert [trace["assistant_outcome"] for trace in traces(posthog_client)] == [
        AssistantTraceOutcome.INTERRUPTED
    ]


def _fail_without_a_model(run: ChatRun) -> None:
    outcome = ChatRunOutcome(
        status=ChatRunStatus.FAILED, error_code=ERROR_MODEL_UNAVAILABLE
    )
    AssistantChatRunType().persist_outcome(run, outcome)


def _sweep_as_not_started(run: ChatRun) -> None:
    ChatRunHandler().fail_not_started_run(run.id)


def _stop_while_queued(run: ChatRun) -> None:
    ChatRunHandler().request_cancel(run.id)


@pytest.mark.parametrize(
    "end_run, status, error_code, outcome",
    [
        (
            _fail_without_a_model,
            "failed",
            ERROR_MODEL_UNAVAILABLE,
            AssistantTraceOutcome.ERROR,
        ),
        (
            _sweep_as_not_started,
            "failed",
            ERROR_NOT_STARTED,
            AssistantTraceOutcome.NOT_STARTED,
        ),
        (_stop_while_queued, "cancelled", "", AssistantTraceOutcome.CANCELLED),
    ],
    ids=["no_model", "no_worker", "stopped"],
)
@pytest.mark.django_db
def test_a_run_that_never_reached_the_agent_tells_the_model_nothing_changed(
    assistant_run,
    posthog_client,
    django_capture_on_commit_callbacks,
    end_run,
    status,
    error_code,
    outcome,
):
    run = assistant_run(content="Add rows")

    with django_capture_on_commit_callbacks(execute=True):
        end_run(run)

    message = ai_message(run)
    [trace] = traces(posthog_client)
    assert (message.content, message.artifacts["run"]) == (
        "",
        {"status": status, "error_code": error_code},
    )
    assert history_texts(run) == ["Add rows", NOT_STARTED_ANSWER]
    assert trace["assistant_outcome"] == outcome
    assert message.prediction.prediction["posthog_trace_id"] == trace["$ai_trace_id"]


@pytest.mark.django_db
def test_absent_result_after_claim_warns_that_changes_may_exist(assistant_run):
    run = ChatRunHandler().claim_run(assistant_run().id)
    AssistantChatRunType().persist_outcome(
        run, ChatRunOutcome(status=ChatRunStatus.FAILED, error_code="failed")
    )
    assert history_texts(run)[-1] == unfinished_answer("")


@pytest.mark.django_db
def test_missing_product_outcome_is_repaired_once_before_run_metadata_can_be_pruned(
    assistant_run,
):
    run = ChatRunHandler().claim_run(assistant_run(content="Change rows").id)
    run.status, run.error_code = ChatRunStatus.FAILED, "persist_failed"
    run.save(update_fields=["status", "error_code"])
    adapter = AssistantChatRunType()

    assert adapter.ensure_interruption_warning(run) is True
    assert adapter.ensure_interruption_warning(run) is True

    assert history_texts(run) == ["Change rows", unfinished_answer("")]
    human = _chat(run).messages.get(id=run.context["human_message_id"])
    assert human.artifacts["run_warning"]["run_id"] == str(run.id)
    run.delete()
    assert history_texts(run) == ["Change rows", unfinished_answer("")]


@pytest.mark.django_db
def test_serialized_outcome_uses_its_saved_message_and_current_feedback(assistant_run):
    from baserow.core.chat_runs.service import serialize_run
    from baserow_enterprise.assistant.models import AssistantChatMessage

    run = assistant_run()
    adapter = AssistantChatRunType()
    run.outcome = adapter.persist_outcome(
        run,
        ChatRunOutcome(
            status=ChatRunStatus.COMPLETED,
            result=AssistantRunResult(text="Original answer", message_history=b"[]"),
        ),
    )
    run.status = ChatRunStatus.COMPLETED
    run.save(update_fields=["outcome", "status"])
    saved = ai_message(run)
    prediction = saved.prediction
    prediction.human_sentiment = 1
    prediction.save(update_fields=["human_sentiment"])
    AssistantChat.objects.filter(id=run.chat_id).update(title="Current title")
    AssistantChatMessage.objects.create(
        chat_id=run.chat_id, role="ai", content="Later answer"
    )

    message = serialize_run(run)["message"]

    assert message["id"] == saved.id
    assert message["content"] == "Original answer"
    assert message["human_sentiment"] == "LIKE"
    assert message["can_submit_feedback"] is True
    assert message["chat_title"] == "Current title"
    run.refresh_from_db()
    assert run.outcome["human_sentiment"] is None
    assert "chat_title" not in run.outcome


@pytest.mark.django_db
def test_removed_product_message_falls_back_to_its_own_durable_outcome(assistant_run):
    from baserow_enterprise.assistant.models import AssistantChatMessage

    run = assistant_run()
    run.outcome = {"id": 87654321, "type": "ai/message", "content": "Durable answer"}
    AssistantChatMessage.objects.create(
        chat_id=run.chat_id, role="ai", content="Later answer"
    )

    message = AssistantChatRunType().serialize_outcome(run)

    assert message == {**run.outcome, "chat_title": _chat(run).title}
    assert "chat_title" not in run.outcome
