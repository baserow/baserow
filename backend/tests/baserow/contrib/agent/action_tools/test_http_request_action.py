import json
from unittest.mock import Mock, patch

import pytest
from requests import exceptions as request_exceptions

from advocate.exceptions import UnacceptableAddressException
from baserow.contrib.agent.action_tools.action_types import (
    HIDDEN_VALUE,
    HTTP_ACTION_MAX_BODY_BYTES,
    HTTP_ACTION_MAX_RESULT_CHARACTERS,
    HTTPRequestAgentActionType,
)
from baserow.contrib.agent.action_tools.service import AgentActionService
from baserow.contrib.agent.action_tools.tools import get_approval_key
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.integrations.core.constants import BODY_TYPE
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.tools.errors import ToolInputError

from ..test_replies import decide, pause, respond, tool_call
from ..utils import run_reply

SEND = "baserow.contrib.integrations.core.service_types.send_http_request"


def answer(body, status_code=200, content_type="application/json"):
    response = Mock()
    response.status_code = status_code
    response.headers = {"Content-Type": content_type}
    if isinstance(body, str):
        response.text = body
        response.json.side_effect = request_exceptions.JSONDecodeError("", "", 0)
    else:
        response.text = json.dumps(body)
        response.json.return_value = body
    return response


def formula(value, mode="simple"):
    return BaserowFormulaObject.create(value, mode=mode)


@pytest.fixture
def http_action(data_fixture, configured_agent):
    """A call_api action pointed at an API, with a fixed key and a model header."""

    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    action = data_fixture.create_agent_action(agent=agent, action_type="http_request")
    trace_id = "b2e1c7d0-0000-4000-8000-000000000001"
    action.inputs.append(
        {
            "id": trace_id,
            "name": "trace",
            "type": "string",
            "description": "A trace id.",
            "required": False,
        }
    )
    action.save()
    AgentActionService().update_action(
        user,
        agent.id,
        action.id,
        service_values={
            "url": formula("'https://api.example.com/orders'", mode="advanced"),
            "headers": [
                {
                    "key": "Authorization",
                    "value": formula("Bearer API_KEY_CANARY", "raw"),
                },
                {"key": "X-Trace", "value": formula(f"get('tool_input.{trace_id}')")},
            ],
        },
    )
    action.refresh_from_db()
    action.service = action.service.specific
    return user, agent, action


def call(name, call_id="http_call", **arguments):
    return tool_call(name, call_id, **{"body": '{"order": 7}', **arguments})


@pytest.mark.django_db
def test_a_new_http_action_is_not_offered_until_it_has_an_url(data_fixture):
    action = data_fixture.create_agent_action(action_type="http_request")
    action_type = HTTPRequestAgentActionType()

    assert action_type.get_configuration_errors(action) == {"url": "required"}
    assert AgentHandler().get_action_tools(action.agent) == []

    action.service.specific.url = formula("'https://api.example.com'", "advanced")
    action.service.specific.save()
    action.refresh_from_db()
    assert action_type.get_configuration_errors(action) == {}


@pytest.mark.django_db
def test_a_header_with_a_missing_input_is_reported_on_the_headers(http_action):
    _, _, action = http_action
    action.inputs.pop()

    assert HTTPRequestAgentActionType().get_configuration_errors(action) == {
        "headers": "invalid"
    }


@pytest.mark.django_db
def test_the_preview_hides_fixed_header_values_and_shows_the_model_ones(
    http_action,
):
    _, _, action = http_action
    action_type = HTTPRequestAgentActionType()

    resolved = action_type.prepare(action, {"body": '{"order": 7}', "trace": "t-1"})
    values = action_type.get_preview(action, resolved)["values"]

    assert values == {
        "http_method": "POST",
        "url": "https://api.example.com/orders",
        "headers": {"Authorization": HIDDEN_VALUE, "X-Trace": "t-1"},
        "body_type": "json",
        "body_content": '{"order": 7}',
    }
    assert "API_KEY_CANARY" not in json.dumps(values)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body,message",
    [
        ('{"order": ', "not valid JSON"),
        (json.dumps({"note": "x" * HTTP_ACTION_MAX_BODY_BYTES}), "larger than 64 KB"),
    ],
)
def test_a_body_that_cannot_be_sent_is_refused_when_prepared(
    http_action, body, message
):
    _, _, action = http_action

    with pytest.raises(ToolInputError, match=message):
        HTTPRequestAgentActionType().prepare(action, {"body": body})


@pytest.mark.django_db
def test_an_invalid_body_neither_waits_for_approval_nor_is_sent(http_action, mocker):
    user, agent, action = http_action
    action.ask_first = True
    action.save()
    respond(mocker, ({0: call(action.name, body="not json")},))

    with patch(SEND) as send:
        reply = pause(user, agent)

    send.assert_not_called()
    assert reply.status == "completed"
    assert reply.steps[0]["status"] == "failed"
    assert reply.transcript.paused_conversation is None


@pytest.mark.django_db
def test_an_approved_call_sends_what_its_step_showed_and_returns_the_answer(
    http_action, mocker
):
    user, agent, action = http_action
    action.ask_first = True
    action.save()
    respond(mocker, ({0: call(action.name, trace="t-9")},))

    with patch(SEND, return_value=answer({"id": 7, "status": "open"})) as send:
        reply = pause(user, agent)
        assert reply.status == "waiting"
        send.assert_not_called()
        shown = reply.steps[0]["input"]["values"]
        run_reply(decide(user, reply, approved=True))

    reply.refresh_from_db()
    kwargs = send.call_args.kwargs
    assert kwargs["method"] == "POST"
    assert kwargs["url"] == shown["url"] == "https://api.example.com/orders"
    assert kwargs["json"] == {"order": 7}
    assert kwargs["headers"]["Authorization"] == "Bearer API_KEY_CANARY"
    assert kwargs["headers"]["X-Trace"] == shown["headers"]["X-Trace"] == "t-9"
    step = reply.steps[0]
    assert (step["presentation_type"], step["status"]) == ("http_request", "done")
    assert "API_KEY_CANARY" not in json.dumps(reply.steps)
    assert "API_KEY_CANARY" not in json.dumps(reply.transcript.model_messages)
    [returned] = [
        part["content"]
        for message in reply.transcript.model_messages
        for part in message["parts"]
        if part["part_kind"] == "tool-return"
    ]
    assert returned == {
        "status_code": 200,
        "content_type": "application/json",
        "body": {"id": 7, "status": "open"},
        "body_omitted": False,
    }


@pytest.mark.django_db
def test_the_model_reads_a_short_answer_whole_and_the_start_of_a_long_one(
    http_action,
):
    _, _, action = http_action
    action_type = HTTPRequestAgentActionType()
    resolved = action_type.prepare(action, {"body": "{}"})

    with patch(SEND, return_value=answer({"id": 7}, status_code=201)):
        result = action_type.get_tool_result(
            action, action_type.dispatch(action, resolved)
        )
    assert result == {
        "status_code": 201,
        "content_type": "application/json",
        "body": {"id": 7},
        "body_omitted": False,
    }

    long_text = "a" * (HTTP_ACTION_MAX_RESULT_CHARACTERS + 10)
    with patch(SEND, return_value=answer(long_text, content_type="text/plain")):
        result = action_type.get_tool_result(
            action, action_type.dispatch(action, resolved)
        )
    assert result["body"] == long_text[:HTTP_ACTION_MAX_RESULT_CHARACTERS]
    assert result["body_truncated"] is True

    with patch(SEND, return_value=answer("%PDF", content_type="application/pdf")):
        result = action_type.get_tool_result(
            action, action_type.dispatch(action, resolved)
        )
    assert (result["body"], result["body_omitted"]) == ("", True)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "failure,message",
    [
        (UnacceptableAddressException(), "can't be called"),
        (request_exceptions.ConnectionError(), "didn't reach the server"),
    ],
)
def test_an_address_that_is_refused_or_unreachable_is_explained(
    http_action, failure, message
):
    _, _, action = http_action
    action_type = HTTPRequestAgentActionType()
    resolved = action_type.prepare(action, {"body": "{}"})

    with patch(SEND, side_effect=failure):
        with pytest.raises(ToolInputError, match=message):
            action_type.dispatch(action, resolved)


@pytest.mark.django_db
def test_a_form_body_previews_its_rows_like_the_headers(http_action):
    user, agent, action = http_action
    trace_id = action.inputs[1]["id"]
    AgentActionService().update_action(
        user,
        agent.id,
        action.id,
        service_values={
            "body_type": BODY_TYPE.FORM,
            "form_data": [
                {"key": "token", "value": formula("FORM_SECRET", "raw")},
                {"key": "trace", "value": formula(f"get('tool_input.{trace_id}')")},
            ],
        },
    )
    action.refresh_from_db()
    action_type = HTTPRequestAgentActionType()

    values = action_type.get_preview(
        action, action_type.prepare(action, {"body": "", "trace": "t-2"})
    )["values"]

    assert values["form_data"] == {"token": HIDDEN_VALUE, "trace": "t-2"}
    assert "body_content" not in values


@pytest.mark.django_db
def test_the_approval_key_reads_the_same_with_several_headers(http_action):
    user, agent, action = http_action
    AgentActionService().update_action(
        user,
        agent.id,
        action.id,
        service_values={
            "headers": [
                {"key": f"X-{number}", "value": formula(f"v{number}", "raw")}
                for number in range(8)
            ],
        },
    )

    keys = set()
    for _ in range(3):
        action.refresh_from_db()
        action.service = action.service.specific
        keys.add(get_approval_key(action))
    assert len(keys) == 1
    assert [header.key for header in action.service.headers.all()] == [
        f"X-{number}" for number in range(8)
    ]
