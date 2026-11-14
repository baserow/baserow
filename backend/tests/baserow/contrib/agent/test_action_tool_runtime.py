import json
from uuid import uuid4

from django.core.mail.backends.locmem import EmailBackend

import pytest

from baserow.contrib.agent.action_tools.registries import (
    AgentActionType,
    agent_action_type_registry,
)
from baserow.contrib.agent.action_tools.service import AgentActionService
from baserow.contrib.agent.constants import (
    DISALLOWED_TOOL_CALL_NOTE,
    TOOL_CHANGED_CALL_NOTE,
)
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.previews import StepPreview
from baserow.contrib.agent.service import AgentService
from baserow.core.chat_runs.models import ChatRun
from baserow.core.services.types import DispatchResult
from baserow.core.trash.handler import TrashHandler

from .test_replies import decide, pause, respond, tool_call
from .utils import run_reply


@pytest.fixture
def email_action(data_fixture, configured_agent, mocker, mailoutbox):
    """A real configured service using an in-memory transport, never SMTP."""

    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    action = data_fixture.create_agent_action(agent=agent)
    integration = data_fixture.create_smtp_integration(
        application=agent, username="sender", password="SMTP_SECRET_CANARY"
    )
    service = action.service.specific
    service.integration = integration
    service.use_instance_smtp_settings = False
    service.from_email = {"formula": "'sender@example.com'"}
    service.save()
    action.service = service
    connection = mocker.patch(
        "baserow.contrib.integrations.core.service_types.get_connection",
        return_value=EmailBackend(),
    )
    return user, agent, action, integration, connection


def email_call(name, call_id="email_call", **changes):
    return tool_call(
        name,
        call_id,
        **{
            "to_email": "alice@example.com",
            "subject": "Hello Alice",
            "body": "The report is ready.",
            **changes,
        },
    )


@pytest.mark.django_db
def test_email_runs_without_workspace_access_and_uses_shared_activity(
    email_action, mocker, mailoutbox
):
    user, agent, action, _, connection = email_action
    assert agent.run_as_subject_id is None
    respond(mocker, ({0: email_call(action.name)},))

    reply = pause(user, agent)

    assert reply.status == "completed"
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["alice@example.com"]
    assert mailoutbox[0].subject == "Hello Alice"
    assert mailoutbox[0].body == "The report is ready."
    assert connection.call_args.kwargs["password"] == "SMTP_SECRET_CANARY"
    step = reply.steps[0]
    assert (step["tool"], step["presentation_type"], step["status"]) == (
        action.name,
        "smtp_email",
        "done",
    )
    assert "alice@example.com" in json.dumps(step["input"])
    assert "SMTP_SECRET_CANARY" not in json.dumps(reply.transcript.model_messages)
    assert "SMTP_SECRET_CANARY" not in json.dumps(reply.steps)


@pytest.mark.django_db
def test_only_configured_enabled_actions_are_available(email_action):
    _, agent, action, _, _ = email_action
    handler = AgentHandler()
    assert [tool.type for tool in handler.get_action_tools(agent)] == [action.name]

    action.enabled = False
    action.save()
    assert handler.get_action_tools(agent) == []

    action.enabled = True
    action.ask_first = True
    action.save()
    assert len(handler.get_action_tools(agent)) == 1

    action.service.integration = None
    action.service.save()
    assert handler.get_action_tools(agent) == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "mutation", ["rename", "edit_service", "edit_inputs", "edit_integration"]
)
def test_an_approved_email_does_not_send_when_its_action_changed(
    email_action, mocker, mailoutbox, mutation
):
    user, agent, action, integration, connection = email_action
    action.ask_first = True
    action.save()
    received = respond(mocker, ({0: email_call(action.name)},))
    reply = pause(user, agent)
    assert reply.status == "waiting"
    assert "alice@example.com" in json.dumps(reply.steps[0]["input"])

    changes = {
        "rename": {"name": "renamed_email"},
        "edit_service": {"service_values": {"body_type": "html"}},
        "edit_inputs": {
            "inputs": [
                {**action.inputs[0], "description": "Changed"},
                *action.inputs[1:],
            ]
        },
    }.get(mutation)
    if mutation == "edit_integration":
        integration.host = "smtp.other.example"
        integration.save()
    else:
        AgentActionService().update_action(user, agent.id, action.id, **changes)
    run_reply(decide(user, reply, approved=True))

    reply.refresh_from_db()
    assert mailoutbox == []
    connection.assert_not_called()
    assert [step["status"] for step in reply.steps] == ["failed"]
    expected = (
        DISALLOWED_TOOL_CALL_NOTE if mutation == "rename" else TOOL_CHANGED_CALL_NOTE
    )
    assert [
        (part.tool_call_id, part.outcome, part.content)
        for part in received[-1][-1].parts
    ] == [("email_call", "denied", expected)]


@pytest.mark.django_db
@pytest.mark.parametrize("ask_first", [False, True])
def test_a_call_sends_the_values_its_step_shows(
    email_action, mocker, mailoutbox, ask_first
):
    user, agent, action, _, _ = email_action
    AgentActionService().update_action(
        user,
        agent.id,
        action.id,
        ask_first=ask_first,
        service_values={
            "body": {"formula": "concat('Code ', generate_uuid())", "mode": "advanced"}
        },
    )
    respond(mocker, ({0: email_call(action.name)},))

    reply = pause(user, agent)
    shown = reply.steps[0]["input"]["values"]["body"]
    if ask_first:
        assert mailoutbox == []
        run_reply(decide(user, reply, approved=True))
        reply.refresh_from_db()

    assert reply.steps[0]["input"]["values"]["body"] == shown
    assert [email.body for email in mailoutbox] == [shown]


@pytest.mark.django_db
def test_an_approved_call_without_its_approved_values_does_not_send(
    email_action, mocker, mailoutbox
):
    user, agent, action, _, connection = email_action
    action.ask_first = True
    action.save()
    respond(mocker, ({0: email_call(action.name)},))
    reply = pause(user, agent)
    transcript = reply.transcript
    assert transcript.paused_conversation["deferred_tool_requests"]["metadata"]
    transcript.paused_conversation["deferred_tool_requests"]["metadata"] = {}
    transcript.save()

    run_reply(decide(user, reply, approved=True))

    reply.refresh_from_db()
    assert reply.steps[0]["status"] == "failed"
    assert mailoutbox == []
    connection.assert_not_called()


@pytest.mark.django_db
def test_inputs_named_like_the_tool_context_and_whole_numbers_are_sent_as_given(
    email_action, mocker, mailoutbox
):
    user, agent, action, _, _ = email_action
    quantity = str(uuid4())
    inputs = [
        *action.inputs[:2],
        {**action.inputs[2], "name": "run_ctx"},
        {
            "id": quantity,
            "name": "quantity",
            "type": "number",
            "description": "",
            "required": True,
        },
    ]
    AgentActionService().update_action(
        user,
        agent.id,
        action.id,
        inputs=inputs,
        service_values={
            "subject": {
                "formula": f"concat('Qty: ', get('tool_input.{quantity}'))",
                "mode": "advanced",
            }
        },
    )
    respond(
        mocker,
        (
            {
                0: tool_call(
                    action.name,
                    "call",
                    to_email="alice@example.com",
                    subject="Ignored",
                    run_ctx="The body",
                    quantity=5,
                )
            },
        ),
    )

    reply = pause(user, agent)

    assert reply.status == "completed"
    assert [(email.subject, email.body) for email in mailoutbox] == [
        ("Qty: 5", "The body")
    ]


@pytest.mark.django_db
def test_each_held_email_keeps_its_own_payload(email_action, mocker, mailoutbox):
    user, agent, action, _, _ = email_action
    action.ask_first = True
    action.save()
    respond(
        mocker,
        (
            {
                0: email_call(action.name, "first"),
                1: email_call(
                    action.name, "second", to_email="bob@example.com", body="Second"
                ),
            },
        ),
    )
    reply = pause(user, agent)
    assert reply.status == "waiting"
    result = AgentService().decide_approvals(
        user,
        agent.id,
        reply.conversation.uuid,
        [{"id": approval.id, "approved": True} for approval in reply.approvals.all()],
    )
    run_reply(ChatRun.objects.get(id=result.run_id))

    assert [(email.to, email.body) for email in mailoutbox] == [
        (["alice@example.com"], "The report is ready."),
        (["bob@example.com"], "Second"),
    ]


@pytest.mark.django_db
def test_always_allow_follows_action_identity_not_reused_name(
    email_action, data_fixture, mocker, mailoutbox
):
    user, agent, action, _, _ = email_action
    action.ask_first = True
    action.save()
    old_name = action.name
    respond(mocker, ({0: email_call(old_name)},))
    reply = pause(user, agent)
    action.service.delete()
    replacement = data_fixture.create_agent_action(
        agent=agent, name=old_name, ask_first=True
    )

    result = AgentService().decide_approvals(
        user,
        agent.id,
        reply.conversation.uuid,
        [{"id": reply.approvals.get().id, "approved": True}],
        always_allow=True,
    )
    run_reply(ChatRun.objects.get(id=result.run_id))

    replacement.refresh_from_db()
    assert replacement.ask_first is True
    assert result.always_allowed_tools == []
    assert mailoutbox == []


@pytest.mark.django_db
def test_always_allow_stops_the_approved_action_asking_first(
    email_action, mocker, mailoutbox
):
    user, agent, action, _, _ = email_action
    action.ask_first = True
    action.save()
    respond(mocker, ({0: email_call(action.name)},))
    reply = pause(user, agent)

    result = AgentService().decide_approvals(
        user,
        agent.id,
        reply.conversation.uuid,
        [{"id": reply.approvals.get().id, "approved": True}],
        always_allow=True,
    )
    run_reply(ChatRun.objects.get(id=result.run_id))

    action.refresh_from_db()
    assert action.ask_first is False
    assert result.always_allowed_tools == [action.name]
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_pending_email_does_not_send_once_its_integration_is_trashed(
    email_action, mocker, mailoutbox
):
    user, agent, action, integration, connection = email_action
    action.ask_first = True
    action.save()
    respond(mocker, ({0: email_call(action.name)},))
    reply = pause(user, agent)
    TrashHandler.trash(user, agent.workspace, agent, integration)

    run_reply(decide(user, reply, approved=True))

    reply.refresh_from_db()
    assert reply.steps[0]["status"] == "failed"
    assert mailoutbox == []
    connection.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("ask_first", [False, True])
def test_invalid_resolved_recipient_explains_the_input_error_without_sending(
    email_action, mocker, mailoutbox, ask_first
):
    user, agent, action, _, connection = email_action
    action.inputs[0]["type"] = "string"
    action.ask_first = ask_first
    action.save()
    respond(mocker, ({0: email_call(action.name, to_email="not-an-email")},))

    reply = pause(user, agent)

    assert reply.status == "completed"
    assert not reply.approvals.exists()
    assert reply.steps[0]["status"] == "failed"
    assert reply.steps[0]["error_code"] == "invalid_input"
    assert "Enter a valid email address" in reply.steps[0]["error_message"]
    assert "to_emails" in reply.steps[0]["error_message"]
    assert mailoutbox == []
    connection.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "changes", [{"to_email": "not-an-email"}, {"subject": 42}, {"unknown": True}]
)
def test_invalid_action_arguments_neither_send_nor_wait_for_approval(
    email_action, mocker, mailoutbox, changes
):
    user, agent, action, _, connection = email_action
    action.ask_first = True
    action.save()
    respond(mocker, ({0: email_call(action.name, **changes)},))

    reply = pause(user, agent)

    assert reply.status == "completed"
    assert not reply.approvals.exists()
    assert reply.steps[0]["status"] == "failed"
    assert reply.steps[0]["error_code"] == "invalid_input"
    assert mailoutbox == []
    connection.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("ask_first", [False, True])
def test_runtime_shows_the_adapter_preview_and_dispatches_the_arguments(
    email_action, mocker, monkeypatch, ask_first
):
    user, agent, action, _, connection = email_action
    action.inputs = [
        {
            "id": str(uuid4()),
            "name": "payload",
            "type": "string",
            "description": "The payload for the destination.",
            "required": True,
        }
    ]
    action.ask_first = ask_first
    action.save()
    preview = StepPreview(names={"target": "#reports"}).to_input()
    dispatched = []

    class GenericActionType(AgentActionType):
        # Reuse a service row while replacing only the small action adapter.
        type = "smtp_email"

        def get_defaults(self):
            return {}

        def get_preview_values(self, service, resolved_values):
            return {}

        def get_configuration_errors(self, action):
            return {}

        def prepare(self, action, arguments):
            return {"payload": arguments["payload"]}

        def get_preview(self, action, resolved_values):
            return preview

        def dispatch(self, action, resolved_values):
            dispatched.append(resolved_values)
            return DispatchResult(data={"queued": True})

    monkeypatch.setitem(
        agent_action_type_registry.registry, "smtp_email", GenericActionType()
    )
    respond(mocker, ({0: tool_call(action.name, "generic_call", payload="Hi")},))

    reply = pause(user, agent)

    if ask_first:
        assert reply.status == "waiting"
        assert reply.steps[0]["input"] == preview
        assert dispatched == []
        run_reply(decide(user, reply, approved=True))
        reply.refresh_from_db()

    assert reply.status == "completed"
    assert dispatched == [{"payload": "Hi"}]
    assert reply.steps[0]["input"] == preview
    connection.assert_not_called()
