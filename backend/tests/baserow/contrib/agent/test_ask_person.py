from collections.abc import AsyncIterator
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import AbstractUser
from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel
from pytest_mock import MockerFixture

from baserow.contrib.agent.constants import (
    ASK_PERSON_ANSWER_MAX_LENGTH,
    ASK_PERSON_DISMISSED_HISTORY,
    ASK_PERSON_DISMISSED_NOTE,
    ASK_PERSON_QUESTION_MAX_LENGTH,
    ASK_PERSON_TOOL_NAME,
    TRIGGER_CONVERSATION_INSTRUCTIONS,
    UNATTENDED_ASK_PERSON_INSTRUCTIONS,
    UNATTENDED_NO_PERSON_INSTRUCTIONS,
)
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import (
    AgentApplication,
    AgentMessage,
    AgentReplyStatus,
    AgentToolApproval,
)
from baserow.contrib.agent.permission_manager import (
    AgentParticipationPermissionManagerType,
)
from baserow.contrib.agent.replies import build_history, name_sender
from baserow.contrib.agent.service import AgentService
from baserow.contrib.agent.types import AgentConversationUser
from baserow.core.chat_runs.models import ChatRun

from .test_action_tool_runtime import email_call
from .test_replies import (
    add_row,
    allow_tools,
    reply_state,
    respond,
    row_names,
    run_of,
    start,
    tool_call,
)
from .test_tool_approvals import decide, statuses
from .utils import run_reply


def ask(question: str = "Which customer is this about?") -> dict[int, DeltaToolCall]:
    return {0: tool_call(ASK_PERSON_TOOL_NAME, "call_ask", question=question)}


def respond_offering(
    mocker: MockerFixture,
) -> tuple[list[list[ModelMessage]], list[list[str]]]:
    """
    Have the model answer every request with text.

    :param mocker: Patches the reply's model.
    :return: The messages of each request, and the tools it offered.
    """

    received: list[list[ModelMessage]] = []
    offered: list[list[str]] = []

    async def stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str]:
        received.append(messages)
        offered.append([tool.name for tool in info.function_tools])
        yield "Done."

    mocker.patch(
        "baserow.contrib.agent.chat_run_type.create_reply_model",
        return_value=(FunctionModel(stream_function=stream), {}),
    )
    return received, offered


def trigger_reply(
    data_fixture, agent: AgentApplication, **trigger_values: object
) -> AgentMessage:
    trigger = data_fixture.create_agent_trigger(agent=agent, **trigger_values)
    conversation = (
        AgentHandler().start_trigger_conversation(trigger, "Tick").conversation
    )
    run_reply(run_of(conversation))
    return AgentMessage.objects.get(conversation=conversation, role="assistant")


def answer(user: AbstractUser, reply: AgentMessage, **decision: object) -> ChatRun:
    conversation = reply.conversation
    approval = reply.approvals.get(status="pending")
    result = AgentService().decide_approvals(
        user,
        conversation.agent_id,
        conversation.uuid,
        [{"id": approval.id, **decision}],
    )
    return ChatRun.objects.get(id=result.run_id)


def follow_up(user: AbstractUser, reply: AgentMessage) -> None:
    conversation = reply.conversation
    # Without RBAC nobody may continue a triggered conversation.
    with patch.object(
        AgentParticipationPermissionManagerType,
        "check_multiple_permissions",
        return_value={},
    ):
        created = AgentService().create_message(
            user, conversation.agent_id, conversation.uuid, uuid4(), "And now?"
        )
        run_reply(ChatRun.objects.get(id=created.run_id))


def named(user: AbstractUser, content: str) -> str:
    """A triggered conversation is shared, so the model reads who wrote each line."""

    return name_sender(content, AgentConversationUser.of(user))


def told_about_question(messages: list[ModelMessage]) -> list[str]:
    return [
        part.content
        for message in messages
        for part in getattr(message, "parts", [])
        if getattr(part, "tool_name", None) == ASK_PERSON_TOOL_NAME
        and part.part_kind == "tool-return"
    ]


@pytest.mark.django_db
def test_a_triggered_run_waits_for_its_question_and_continues_with_the_answer(
    data_fixture, configured_agent, mocker
):
    agent = configured_agent()
    received = respond(mocker, (ask(),))

    reply = trigger_reply(data_fixture, agent)

    assert reply_state(reply.id) == ("waiting", "", "")
    assert reply.approvals.get().tool_name == ASK_PERSON_TOOL_NAME
    member = data_fixture.create_user(workspace=agent.workspace)
    run_reply(answer(member, reply, approved=True, answer="Acme"))
    assert reply_state(reply.id) == ("completed", "", "Done.")
    assert reply.approvals.get().answer == "Acme"
    assert told_about_question(received[-1]) == ["Acme"]


@pytest.mark.django_db
def test_a_dismissed_question_tells_the_agent_nobody_will_answer(
    data_fixture, configured_agent, mocker
):
    agent = configured_agent()
    received = respond(mocker, (ask(),))
    reply = trigger_reply(data_fixture, agent)
    member = data_fixture.create_user(workspace=agent.workspace)

    run_reply(answer(member, reply, approved=False))

    assert reply_state(reply.id) == ("completed", "", "Done.")
    assert reply.approvals.get().status == "rejected"
    assert told_about_question(received[-1]) == [ASK_PERSON_DISMISSED_NOTE]


@pytest.mark.django_db
@pytest.mark.parametrize("may_ask_person", [True, False])
def test_unattended_instructions_name_the_trigger_and_say_whether_it_may_ask(
    data_fixture, configured_agent, mocker, may_ask_person
):
    agent = configured_agent()
    received, offered = respond_offering(mocker)

    trigger_reply(data_fixture, agent, name="Orders", may_ask_person=may_ask_person)

    instructions = received[0][-1].instructions
    assert 'The trigger "Orders" started this reply' in instructions
    assert (UNATTENDED_ASK_PERSON_INSTRUCTIONS in instructions) is may_ask_person
    assert (UNATTENDED_NO_PERSON_INSTRUCTIONS in instructions) is not may_ask_person
    assert (ASK_PERSON_TOOL_NAME in offered[0]) is may_ask_person


@pytest.mark.django_db
def test_unattended_instructions_of_an_unnamed_trigger_name_no_trigger(
    data_fixture, configured_agent, mocker
):
    agent = configured_agent()
    received, _ = respond_offering(mocker)

    trigger_reply(data_fixture, agent, name="")

    instructions = received[0][-1].instructions
    assert "A trigger started this reply" in instructions
    assert '"Trigger"' not in instructions


@pytest.mark.django_db
def test_a_private_conversation_and_a_follow_up_never_offer_the_question_tool(
    data_fixture, configured_agent, mocker
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    received, offered = respond_offering(mocker)

    run_reply(run_of(start(user, agent).conversation))
    follow_up(user, trigger_reply(data_fixture, agent, name="Orders"))

    unattended = 'The trigger "Orders" started this reply'
    assert [ASK_PERSON_TOOL_NAME in tools for tools in offered] == [
        False,
        True,
        False,
    ]
    assert [unattended in messages[-1].instructions for messages in received] == [
        False,
        True,
        False,
    ]


@pytest.mark.django_db
def test_a_follow_up_in_a_triggered_conversation_is_still_told_its_opening_message_is_data(
    data_fixture, configured_agent, mocker
):
    agent = configured_agent()
    received, _ = respond_offering(mocker)
    member = data_fixture.create_user(workspace=agent.workspace)

    follow_up(member, trigger_reply(data_fixture, agent))

    assert TRIGGER_CONVERSATION_INSTRUCTIONS in received[-1][-1].instructions


@pytest.mark.django_db
def test_a_question_turned_off_while_waiting_still_gets_its_answer(
    data_fixture, configured_agent, mocker
):
    agent = configured_agent()
    received = respond(mocker, (ask(),))
    reply = trigger_reply(data_fixture, agent)
    trigger = reply.conversation.trigger
    trigger.may_ask_person = False
    trigger.save(update_fields=["may_ask_person"])
    member = data_fixture.create_user(workspace=agent.workspace)

    run_reply(answer(member, reply, approved=True, answer="Acme"))

    assert reply_state(reply.id) == ("completed", "", "Done.")
    assert told_about_question(received[-1]) == ["Acme"]


@pytest.mark.django_db
def test_a_change_after_a_question_in_the_same_response_waits_for_it(
    data_fixture, configured_agent, mocker
):
    agent = configured_agent()
    table = allow_tools(data_fixture, agent)
    respond(mocker, ({**ask(), 1: add_row(table)},))

    reply = trigger_reply(data_fixture, agent)

    assert reply_state(reply.id) == ("waiting", "", "")
    assert sorted(reply.approvals.values_list("tool_name", flat=True)) == [
        ASK_PERSON_TOOL_NAME,
        "create_rows",
    ]
    assert row_names(table) == []


@pytest.mark.django_db
def test_an_answer_and_a_held_action_of_the_same_response_both_reach_the_resume(
    data_fixture, email_action, mocker, mailoutbox
):
    user, agent, action, _, _ = email_action
    received = respond(mocker, ({**ask(), 1: email_call(action.name)},))
    reply = trigger_reply(data_fixture, agent)
    question = reply.approvals.get(tool_name=ASK_PERSON_TOOL_NAME)
    email = reply.approvals.get(tool_name=action.name)

    result = AgentService().decide_approvals(
        user,
        agent.id,
        reply.conversation.uuid,
        [
            {"id": question.id, "approved": True, "answer": "Acme"},
            {"id": email.id, "approved": True},
        ],
    )
    run_reply(ChatRun.objects.get(id=result.run_id))

    assert reply_state(reply.id) == ("completed", "", "Done.")
    assert told_about_question(received[-1]) == ["Acme"]
    assert [sent.to for sent in mailoutbox] == [["alice@example.com"]]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "question",
    ["", "  \n ", "a" * (ASK_PERSON_QUESTION_MAX_LENGTH + 1)],
    ids=["empty", "blank", "too-long"],
)
def test_a_question_out_of_bounds_is_retried_instead_of_held(
    data_fixture, configured_agent, mocker, question
):
    agent = configured_agent()
    received = respond(mocker, (ask(question),))

    reply = trigger_reply(data_fixture, agent)

    assert reply_state(reply.id) == ("completed", "", "Done.")
    assert not reply.approvals.exists()
    assert [
        part.part_kind
        for message in received[-1]
        for part in getattr(message, "parts", [])
        if getattr(part, "tool_name", None) == ASK_PERSON_TOOL_NAME
    ] == ["tool-call", "retry-prompt"]


@pytest.mark.django_db
def test_a_long_question_reaches_its_step_whole(data_fixture, configured_agent, mocker):
    agent = configured_agent()
    question = "Which customer is this about? " + "a" * 3000
    respond(mocker, (ask(question),))

    reply = trigger_reply(data_fixture, agent)

    assert [
        step["input"] for step in reply.steps if step["tool"] == ASK_PERSON_TOOL_NAME
    ] == [{"question": question}]


@pytest.fixture
def held_question(data_fixture, configured_agent, api_user) -> AgentMessage:
    """A reply in the API user's conversation, holding a question and a create."""

    agent = configured_agent(user=api_user)
    allow_tools(data_fixture, agent, ask_first=("create_rows",))
    conversation = data_fixture.create_agent_conversation(user=api_user, agent=agent)
    data_fixture.create_agent_message(conversation=conversation, content="Tick")
    reply = data_fixture.create_agent_message(
        conversation=conversation,
        role=AgentMessage.Role.ASSISTANT,
        status=AgentReplyStatus.WAITING,
        content="",
    )
    for tool_name in (ASK_PERSON_TOOL_NAME, "create_rows"):
        data_fixture.create_agent_tool_approval(reply=reply, tool_name=tool_name)
    return reply


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tool_name,decision,error",
    [
        (ASK_PERSON_TOOL_NAME, {"approved": True}, "ERROR_AGENT_TOOL_DECISION_INVALID"),
        (
            ASK_PERSON_TOOL_NAME,
            {"approved": True, "answer": " "},
            "ERROR_AGENT_TOOL_DECISION_INVALID",
        ),
        (
            "create_rows",
            {"approved": True, "answer": "Acme"},
            "ERROR_AGENT_TOOL_DECISION_INVALID",
        ),
        (
            ASK_PERSON_TOOL_NAME,
            {"approved": False, "answer": "Acme"},
            "ERROR_REQUEST_BODY_VALIDATION",
        ),
        (
            ASK_PERSON_TOOL_NAME,
            {"approved": False, "reason": "Nobody knows"},
            "ERROR_AGENT_TOOL_DECISION_INVALID",
        ),
        (
            ASK_PERSON_TOOL_NAME,
            {"approved": True, "answer": "a" * (ASK_PERSON_ANSWER_MAX_LENGTH + 1)},
            "ERROR_REQUEST_BODY_VALIDATION",
        ),
    ],
    ids=[
        "no-answer",
        "blank-answer",
        "not-a-question",
        "dismissal-with-answer",
        "dismissal-with-reason",
        "long-answer",
    ],
)
def test_an_answer_is_validated_against_the_held_call(
    api_client, held_question, tool_name, decision, error
):
    approval = held_question.approvals.get(tool_name=tool_name)

    response = decide(api_client, held_question, {"id": approval.id, **decision})

    assert (response.status_code, response.json()["error"]) == (400, error)
    assert statuses(held_question) == ("waiting", ["pending", "pending"])


@pytest.mark.django_db
def test_always_allowing_an_answered_question_changes_no_tool(
    api_client, held_question
):
    agent = held_question.conversation.agent
    configuration = AgentHandler().get_tool_configuration(agent)
    question = held_question.approvals.get(tool_name=ASK_PERSON_TOOL_NAME)

    response = decide(
        api_client,
        held_question,
        {"id": question.id, "approved": True, "answer": "Acme"},
        always_allow=True,
    )

    assert response.status_code == 200
    assert AgentHandler().get_tool_configuration(agent) == configuration
    question.refresh_from_db()
    assert (question.status, question.answer) == (
        AgentToolApproval.Status.APPROVED,
        "Acme",
    )


def turns(messages: list[ModelMessage]) -> list[tuple[str, object]]:
    return [
        (part.part_kind, part.content) for message in messages for part in message.parts
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "decision,told",
    [
        ({"approved": True, "answer": "Acme"}, "Acme"),
        ({"approved": False}, None),
    ],
    ids=["answered", "dismissed"],
)
def test_a_follow_up_sees_the_decided_question_as_plain_turns(
    data_fixture, configured_agent, mocker, decision, told
):
    agent = configured_agent()
    received = respond(mocker, (ask(),))
    reply = trigger_reply(data_fixture, agent)
    member = data_fixture.create_user(workspace=agent.workspace)
    run_reply(answer(member, reply, **decision))

    follow_up(member, reply)

    assert turns(received[-1]) == [
        ("user-prompt", "Tick"),
        ("text", "Which customer is this about?"),
        ("user-prompt", named(member, told) if told else ASK_PERSON_DISMISSED_HISTORY),
        ("text", "Done."),
        ("user-prompt", named(member, "And now?")),
    ]


@pytest.mark.django_db
def test_a_second_question_in_the_same_run_sees_the_first_answer(
    data_fixture, configured_agent, mocker
):
    agent = configured_agent()
    second = {0: tool_call(ASK_PERSON_TOOL_NAME, "call_ask_2", question="Which one?")}
    received = respond(mocker, (ask(),), (second,))
    reply = trigger_reply(data_fixture, agent)
    member = data_fixture.create_user(workspace=agent.workspace)

    run_reply(answer(member, reply, approved=True, answer="Acme"))
    run_reply(answer(member, reply, approved=True, answer="The first"))

    assert reply_state(reply.id) == ("completed", "", "Done.")
    assert [told_about_question(messages) for messages in received] == [
        [],
        ["Acme"],
        ["Acme", "The first"],
    ]

    follow_up(member, reply)

    assert turns(received[-1]) == [
        ("user-prompt", "Tick"),
        ("text", "Which customer is this about?"),
        ("user-prompt", named(member, "Acme")),
        ("text", "Which one?"),
        ("user-prompt", named(member, "The first")),
        ("text", "Done."),
        ("user-prompt", named(member, "And now?")),
    ]


def reply_after_questions(
    data_fixture, agent: AgentApplication, user: AbstractUser, count: int
) -> AgentMessage:
    """
    Create a follow-up reply after earlier replies that each asked a question that
    was answered.

    :param data_fixture: Creates the conversation, messages and approvals.
    :param agent: The Agent the conversation belongs to.
    :param user: The conversation's owner.
    :param count: How many earlier replies asked a question.
    :return: The follow-up reply, not run yet.
    """

    conversation = data_fixture.create_agent_conversation(user=user, agent=agent)
    for index in range(count):
        data_fixture.create_agent_message(conversation=conversation, content="Tick")
        earlier = data_fixture.create_agent_message(
            conversation=conversation,
            role=AgentMessage.Role.ASSISTANT,
            status=AgentReplyStatus.COMPLETED,
            content="Done.",
            steps=[
                {
                    "id": "step_ask",
                    "tool": ASK_PERSON_TOOL_NAME,
                    "input": {"question": f"Question {index}?"},
                }
            ],
        )
        data_fixture.create_agent_tool_approval(
            reply=earlier,
            tool_name=ASK_PERSON_TOOL_NAME,
            step_id="step_ask",
            status=AgentToolApproval.Status.APPROVED,
            answer=f"Answer {index}",
        )
    data_fixture.create_agent_message(conversation=conversation, content="And now?")
    return data_fixture.create_agent_message(
        conversation=conversation,
        role=AgentMessage.Role.ASSISTANT,
        status=AgentReplyStatus.QUEUED,
        content="",
    )


def load_history(reply: AgentMessage) -> tuple[int, list[tuple[str, object]]]:
    with CaptureQueriesContext(connection) as queries:
        handler = AgentHandler()
        request = handler.get_reply_request(handler.get_reply(reply.id))
        history = build_history(request.history)
    return len(queries), turns(history)


@pytest.mark.django_db
def test_loading_the_history_does_not_query_per_answered_question(
    data_fixture, configured_agent
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    load_history(reply_after_questions(data_fixture, agent, user, 1))

    one_count, one_turns = load_history(
        reply_after_questions(data_fixture, agent, user, 1)
    )
    three_count, three_turns = load_history(
        reply_after_questions(data_fixture, agent, user, 3)
    )

    assert (len(one_turns), len(three_turns)) == (4, 12)
    assert three_count == one_count
