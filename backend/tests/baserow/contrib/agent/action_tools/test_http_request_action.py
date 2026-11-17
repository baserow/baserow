import json
from unittest.mock import Mock, patch

from django.db import connection

import pytest
from requests import exceptions as request_exceptions

from advocate.exceptions import UnacceptableAddressException
from baserow.contrib.agent.action_tools.action_types import (
    HIDDEN_VALUE,
    HTTP_ACTION_MAX_REQUEST_BYTES,
    HTTP_ACTION_MAX_RESULT_CHARACTERS,
    HTTPRequestAgentActionType,
)
from baserow.contrib.agent.action_tools.service import AgentActionService
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.integrations.core.constants import BODY_TYPE
from baserow.contrib.integrations.core.models import HTTPHeader
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.services.exceptions import (
    RedirectNotAllowedDispatchException,
    ResponseTooLargeDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.tools.errors import ToolErrorCode, classify_tool_error

from ..test_replies import decide, pause, respond, tool_call
from ..utils import run_reply

SEND = "baserow.contrib.integrations.core.service_types.send_http_request"
TRACE_ID = "b2e1c7d0-0000-4000-8000-000000000001"
TRACE = f"get('tool_input.{TRACE_ID}')"


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


def raw(value):
    return BaserowFormulaObject.create(value, mode="raw")


def formula(value):
    return BaserowFormulaObject.create(value, mode="advanced")


def update(http_action, **service_values):
    user, agent, action = http_action
    AgentActionService().update_action(
        user, agent.id, action.id, service_values=service_values
    )
    action.refresh_from_db()
    action.service = action.service.specific
    return action


def code_of(exc):
    return classify_tool_error(exc).code


def secrets_in(value):
    text = json.dumps(value)
    return [secret for secret in ("API_KEY_CANARY", "MIXED_CANARY") if secret in text]


@pytest.fixture
def http_action(data_fixture, configured_agent):
    """
    A call_api action pointed at an API, with a fixed key, a header the model
    fills, and one that mixes both.
    """

    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    action = data_fixture.create_agent_action(agent=agent, action_type="http_request")
    action.inputs.append(
        {
            "id": TRACE_ID,
            "name": "trace",
            "type": "string",
            "description": "A trace id.",
            "required": False,
        }
    )
    action.save()
    update(
        (user, agent, action),
        url=raw("https://api.example.com/orders"),
        headers=[
            {"key": "Authorization", "value": raw("Bearer API_KEY_CANARY")},
            {"key": "X-Trace", "value": formula(TRACE)},
            {"key": "X-Mixed", "value": formula(f"concat('MIXED_CANARY-', {TRACE})")},
        ],
    )
    return user, agent, action


def call(name, call_id="http_call", **arguments):
    return tool_call(name, call_id, **{"body": '{"order": 7}', **arguments})


@pytest.mark.django_db
def test_a_new_http_action_is_not_offered_until_it_has_an_url(data_fixture):
    action = data_fixture.create_agent_action(action_type="http_request")
    action_type = HTTPRequestAgentActionType()

    assert action_type.get_configuration_errors(action) == {"url": "required"}
    assert AgentHandler().get_action_tools(action.agent) == []

    action.service.specific.url = raw("https://api.example.com")
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
@pytest.mark.parametrize("body_type", [BODY_TYPE.NONE, BODY_TYPE.FORM])
def test_a_body_its_body_type_does_not_send_is_neither_checked_nor_resolved(
    http_action, body_type
):
    action = update(http_action, body_type=body_type)
    action.inputs = [item for item in action.inputs if item["name"] != "body"]
    action_type = HTTPRequestAgentActionType()

    assert action_type.get_configuration_errors(action) == {}
    assert "body_content" not in action_type.prepare(action, {"trace": "t-1"})


@pytest.mark.django_db
def test_the_approver_reads_only_what_the_model_chose_and_where_it_goes(
    http_action,
):
    action = update(
        http_action,
        url=raw(
            "https://API_USER:URL_PASSWORD@api.example.com/orders?api_key=URLSECRET"
        ),
    )
    action_type = HTTPRequestAgentActionType()

    arguments = {"body": '{"order": 7}', "trace": "t-1"}
    resolved = action_type.prepare(action, arguments)
    values = action_type.get_preview(action, resolved, arguments)["values"]

    # Each input is read as a header or the body, so none is listed apart.
    assert values == {
        "http_method": "POST",
        "url": f"https://{HIDDEN_VALUE}@api.example.com/{HIDDEN_VALUE}"
        f"?api_key={HIDDEN_VALUE}",
        "headers": {
            "Authorization": HIDDEN_VALUE,
            "X-Trace": "t-1",
            "X-Mixed": HIDDEN_VALUE,
        },
        "body_type": "json",
        "body_content": '{"order": 7}',
    }


@pytest.mark.django_db
def test_a_body_that_mixes_fixed_text_with_an_input_is_hidden(http_action):
    body_id = http_action[2].inputs[0]["id"]
    action = update(
        http_action,
        body_content=formula(
            f"""concat('{{"token": "BODYSECRET", "note": ', """
            f"""to_json(get('tool_input.{body_id}')), '}}')"""
        ),
    )
    action_type = HTTPRequestAgentActionType()

    resolved = action_type.prepare(action, {"body": "hello"})

    assert json.loads(resolved["body_content"]) == {
        "token": "BODYSECRET",
        "note": "hello",
    }
    preview = action_type.get_preview(action, resolved, {"body": "hello"})["values"]
    assert preview["body_content"] == HIDDEN_VALUE
    assert preview["inputs"] == {"body": "hello"}
    assert "body_content" not in action_type.get_held_values(action, resolved)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "arguments,message",
    [
        ({"body": '{"order": '}, "not valid JSON"),
        ({"body": '{"total": NaN}'}, "not valid JSON"),
        ({"body": '{"total": 1e999}'}, "too large"),
        (
            {"body": json.dumps({"note": "x" * HTTP_ACTION_MAX_REQUEST_BYTES})},
            "larger than 64 KB",
        ),
        ({"body": "{}", "trace": "a\r\nX-Injected: 1"}, "line break"),
        ({"body": "{}", "trace": "a \u2192 b"}, "a header can't carry: \u2192"),
    ],
)
def test_a_request_that_cannot_be_sent_is_refused_when_prepared(
    http_action, arguments, message
):
    _, _, action = http_action

    with pytest.raises(Exception, match=message) as error:
        HTTPRequestAgentActionType().prepare(action, arguments)
    assert code_of(error.value) == ToolErrorCode.INVALID_INPUT


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url,message",
    [
        ("api.example.com/orders", "full URL"),
        ("http://[", "full URL"),
        ("https://api.example.com:99999/orders", "full URL"),
        ("https://api.example.com/" + "a" * 9000, "longer than 8 KB"),
    ],
)
def test_a_malformed_or_long_address_is_refused_when_prepared(
    http_action, url, message
):
    action = update(http_action, url=raw(url), headers=[])

    with pytest.raises(Exception, match=message) as error:
        HTTPRequestAgentActionType().prepare(action, {"body": "{}"})
    assert code_of(error.value) == ToolErrorCode.INVALID_INPUT


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url,carries_key,trace,allowed",
    [
        # The model picks the path, the host stays the builder's.
        (f"concat('https://api.example.com/orders/', {TRACE})", True, "7", True),
        # The model picks the host of a request carrying a key.
        (f"concat('https://', {TRACE}, '/orders')", True, "evil.example", False),
        (TRACE, True, "https://evil.example", False),
        # Nothing hidden goes with it, so the model may choose the address.
        (TRACE, False, "https://evil.example", True),
    ],
)
def test_a_request_carrying_hidden_values_only_goes_to_the_builders_host(
    http_action, url, carries_key, trace, allowed
):
    headers = [{"key": "Authorization", "value": raw("Bearer KEY")}]
    action = update(
        http_action, url=formula(url), headers=headers if carries_key else []
    )
    action_type = HTTPRequestAgentActionType()

    if allowed:
        action_type.prepare(action, {"body": "{}", "trace": trace})
    else:
        with pytest.raises(Exception, match="can only be sent to") as error:
            action_type.prepare(action, {"body": "{}", "trace": trace})
        assert code_of(error.value) == ToolErrorCode.INVALID_INPUT


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url,carries_key,errors",
    [
        (f"concat('https://api.example.com/orders/', {TRACE})", True, {}),
        (f"concat('https://', {TRACE}, '/orders')", True, {"url": "fixed_host"}),
        (TRACE, True, {"url": "fixed_host"}),
        (TRACE, False, {}),
    ],
)
def test_the_builder_is_told_when_a_request_with_hidden_values_has_no_fixed_host(
    http_action, url, carries_key, errors
):
    headers = [{"key": "Authorization", "value": raw("Bearer KEY")}]
    action = update(
        http_action, url=formula(url), headers=headers if carries_key else []
    )

    assert HTTPRequestAgentActionType().get_configuration_errors(action) == errors


@pytest.mark.django_db
def test_the_approver_reads_the_inputs_a_fixed_url_mixes_in_but_not_its_path(
    http_action,
):
    action = update(
        http_action,
        url=formula(f"concat('https://hooks.example.com/T000/SECRET/', {TRACE})"),
        headers=[],
    )
    action_type = HTTPRequestAgentActionType()
    arguments = {"body": "{}", "trace": "orders"}

    values = action_type.get_preview(
        action, action_type.prepare(action, arguments), arguments
    )["values"]

    assert values["url"] == f"https://hooks.example.com/{HIDDEN_VALUE}"
    assert values["inputs"] == {"trace": "orders"}


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
def test_an_approved_call_sends_what_was_shown_and_keeps_no_hidden_value(
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
        assert secrets_in(reply.transcript.paused_conversation) == []
        shown = reply.steps[0]["input"]["values"]
        run_reply(decide(user, reply, approved=True))

    reply.refresh_from_db()
    kwargs = send.call_args.kwargs
    assert kwargs["method"] == "POST"
    assert kwargs["url"] == "https://api.example.com/orders"
    assert shown["url"] == f"https://api.example.com/{HIDDEN_VALUE}"
    assert kwargs["json"] == {"order": 7}
    assert kwargs["headers"]["Authorization"] == "Bearer API_KEY_CANARY"
    assert kwargs["headers"]["X-Mixed"] == "MIXED_CANARY-t-9"
    assert kwargs["headers"]["X-Trace"] == shown["headers"]["X-Trace"] == "t-9"
    step = reply.steps[0]
    assert (step["presentation_type"], step["status"]) == ("http_request", "done")
    assert secrets_in(reply.steps) == []
    assert secrets_in(reply.transcript.model_messages) == []
    assert secrets_in(reply.transcript.paused_conversation) == []
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
def test_a_held_call_survives_an_edit_that_ends_where_it_started(http_action, mocker):
    user, agent, action = http_action
    action.ask_first = True
    action.save()
    headers = [
        {"key": header.key, "value": header.value}
        for header in action.service.headers.all()
    ]
    ids_before = list(action.service.headers.values_list("id", flat=True))
    respond(mocker, ({0: call(action.name, trace="t-3")},))

    with patch(SEND, return_value=answer({"id": 7})) as send:
        reply = pause(user, agent)
        update(http_action, headers=[])
        action = update(http_action, headers=headers)
        assert list(action.service.headers.values_list("id", flat=True)) != (ids_before)
        run_reply(decide(user, reply, approved=True))

    reply.refresh_from_db()
    assert reply.steps[0]["status"] == "done"
    assert send.call_args.kwargs["headers"]["X-Trace"] == "t-3"
    assert send.call_args.kwargs["headers"]["Authorization"] == (
        "Bearer API_KEY_CANARY"
    )


@pytest.mark.django_db
def test_the_model_reads_a_short_answer_whole_and_the_start_of_a_long_one(
    http_action,
):
    _, _, action = http_action
    action_type = HTTPRequestAgentActionType()
    resolved = action_type.prepare(action, {"body": "{}"})

    def result_of(response):
        with patch(SEND, return_value=response):
            return action_type.get_tool_result(
                action, action_type.dispatch(action, resolved)
            )

    assert result_of(answer({"id": 7}, status_code=201)) == {
        "status_code": 201,
        "content_type": "application/json",
        "body": {"id": 7},
        "body_omitted": False,
    }

    long_text = "a" * (HTTP_ACTION_MAX_RESULT_CHARACTERS + 10)
    result = result_of(answer(long_text, content_type="text/plain"))
    assert result["body"] == long_text[:HTTP_ACTION_MAX_RESULT_CHARACTERS]
    assert result["body_truncated"] is True

    long_json = {"items": ["b" * 100] * 300}
    result = result_of(answer(long_json))
    assert result["body"] == json.dumps(long_json)[:HTTP_ACTION_MAX_RESULT_CHARACTERS]
    assert result["body_truncated"] is True

    # The raw body of a list leaves its empty items out, so it can't measure it.
    empty_items = [None] * HTTP_ACTION_MAX_RESULT_CHARACTERS
    result = result_of(answer(empty_items))
    assert result["body"] == json.dumps(empty_items)[:HTTP_ACTION_MAX_RESULT_CHARACTERS]
    assert result["body_truncated"] is True

    result = result_of(answer("%PDF", content_type="application/pdf"))
    assert (result["body"], result["body_omitted"]) == ("", True)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "failure,message,code",
    [
        (
            UnacceptableAddressException(),
            "can't be called",
            ToolErrorCode.INVALID_INPUT,
        ),
        (
            request_exceptions.ConnectionError(),
            "didn't reach the API",
            ToolErrorCode.FAILED,
        ),
        (request_exceptions.Timeout(), "within 30 seconds", ToolErrorCode.FAILED),
        (
            ResponseTooLargeDispatchException("too big"),
            "more than this Baserow instance accepts",
            ToolErrorCode.FAILED,
        ),
        (
            request_exceptions.InvalidHeader(),
            "malformed",
            ToolErrorCode.INVALID_INPUT,
        ),
        (
            RedirectNotAllowedDispatchException("elsewhere"),
            "redirected the request to another server",
            ToolErrorCode.FAILED,
        ),
    ],
)
def test_a_failed_request_is_explained(http_action, failure, message, code):
    _, _, action = http_action
    action_type = HTTPRequestAgentActionType()
    resolved = action_type.prepare(action, {"body": "{}"})

    with patch(SEND, side_effect=failure):
        with pytest.raises(Exception, match=message) as error:
            action_type.dispatch(action, resolved)
    assert code_of(error.value) == code


@pytest.mark.django_db
def test_a_form_body_previews_its_rows_like_the_headers(http_action):
    action = update(
        http_action,
        body_type=BODY_TYPE.FORM,
        form_data=[
            {"key": "token", "value": raw("FORM_SECRET")},
            {"key": "trace", "value": formula(TRACE)},
        ],
    )
    action_type = HTTPRequestAgentActionType()

    arguments = {"body": "", "trace": "t-2"}
    values = action_type.get_preview(
        action, action_type.prepare(action, arguments), arguments
    )["values"]

    assert values["form_data"] == {"token": HIDDEN_VALUE, "trace": "t-2"}
    assert "body_content" not in values


@pytest.mark.django_db
def test_rows_read_by_id_whatever_order_the_table_holds_them_in(http_action):
    action = update(http_action, headers=[])
    service = action.service
    last_id = (
        HTTPHeader.objects.order_by("-id").values_list("id", flat=True)[:1] or [0]
    )[0]
    # Stored with the highest ID first, so a read without an order gets them
    # the other way round.
    for number in reversed(range(4)):
        HTTPHeader.objects.create(
            id=last_id + 10 + number,
            service=service,
            key=f"X-{number}",
            value=raw(f"v{number}"),
        )
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT key FROM {HTTPHeader._meta.db_table} WHERE service_id = %s",
            [service.id],
        )
        assert [row[0] for row in cursor.fetchall()] == [f"X-{n}" for n in (3, 2, 1, 0)]

    action.refresh_from_db()
    action.service = action.service.specific
    exported = ServiceHandler().export_service(action.service)["headers"]
    assert [header["key"] for header in exported] == [f"X-{n}" for n in range(4)]


@pytest.mark.django_db
def test_the_keys_of_the_rows_count_towards_the_size_limit(http_action):
    action = update(
        http_action,
        headers=[
            {"key": f"X-{number}-" + "k" * 240, "value": raw("")}
            for number in range(300)
        ],
    )

    with pytest.raises(Exception, match="larger than 64 KB") as error:
        HTTPRequestAgentActionType().prepare(action, {"body": "{}"})
    assert code_of(error.value) == ToolErrorCode.INVALID_INPUT


@pytest.mark.django_db
def test_a_call_only_follows_redirects_that_stay_on_its_host(http_action):
    _, _, action = http_action
    action_type = HTTPRequestAgentActionType()
    resolved = action_type.prepare(action, {"body": "{}"})

    with patch(SEND, return_value=answer({"id": 7})) as send:
        action_type.dispatch(action, resolved)

    assert send.call_args.kwargs["redirects_stay_on_host"] is True
