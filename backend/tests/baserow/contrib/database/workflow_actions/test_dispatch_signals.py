import logging
from contextlib import contextmanager
from unittest.mock import patch

from django.core.cache import cache
from django.urls import reverse

import pytest
from requests import exceptions as request_exceptions
from rest_framework.exceptions import APIException
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_409_CONFLICT,
    HTTP_429_TOO_MANY_REQUESTS,
)

from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.actions import (
    DispatchButtonFieldActionType,
)
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionDispatchError,
)
from baserow.contrib.database.workflow_actions.models import (
    CoreHTTPRequestWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    OpenUrlWorkflowAction,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.contrib.database.workflow_actions.signals import (
    button_field_before_dispatch,
    button_field_dispatched,
    workflow_action_dispatched,
)
from baserow.contrib.database.workflow_actions.types import DispatchOutcome
from baserow.core.action.signals import action_done
from baserow.throttling.types import RateLimit
from tests.baserow.contrib.database.workflow_actions.test_sample_data_capture import (
    mock_advocate_request,
)


@contextmanager
def _received(signal):
    """The kwargs of every send of `signal` while the block runs."""

    calls = []

    def receiver(sender, **kwargs):
        calls.append(kwargs)

    signal.connect(receiver)
    try:
        yield calls
    finally:
        signal.disconnect(receiver)


def _button(data_fixture, user):
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name="People", fields=[("Name", "text", {})]
    )
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    return table, button_field, row


def _add_row_action(data_fixture, button_field, table, value="Ada"):
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.table = table
    service.save()
    service.field_mappings.create(
        field=table.field_set.get(name="Name"), value=f"'{value}'", enabled=True
    )
    return action


def _add_http_action(data_fixture, button_field):
    action = data_fixture.create_database_workflow_action(
        CoreHTTPRequestWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.url = "'http://example.notexist/'"
    service.save()
    return action


@pytest.mark.django_db
def test_each_server_action_sends_what_it_returned(data_fixture):
    user = data_fixture.create_user()
    table, button_field, row = _button(data_fixture, user)
    first = _add_row_action(data_fixture, button_field, table, "first")
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )
    third = _add_row_action(data_fixture, button_field, table, "third")

    with _received(workflow_action_dispatched) as calls:
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    assert [call["workflow_action"].id for call in calls] == [first.id, third.id]
    # Counted over the whole list, so the open URL action in between is 2.
    assert [call["position"] for call in calls] == [1, 3]
    for call in calls:
        assert call["exception"] is None
        assert call["result"] is not None
        assert call["duration_ms"] >= 0
        assert call["dispatch_context"].field == button_field
        assert call["field"] == button_field


@pytest.mark.django_db
def test_a_failed_action_sends_its_exception_and_no_result(data_fixture):
    user = data_fixture.create_user()
    table, button_field, row = _button(data_fixture, user)
    _add_row_action(data_fixture, button_field, table)
    # A delete-row action with no table configured fails at dispatch.
    broken = data_fixture.create_database_workflow_action(
        LocalBaserowDeleteRowWorkflowAction, field=button_field
    )

    with _received(workflow_action_dispatched) as calls:
        with pytest.raises(WorkflowActionDispatchError):
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )

    assert len(calls) == 2
    failed = calls[1]
    assert failed["workflow_action"].id == broken.id
    assert failed["position"] == 2
    assert failed["result"] is None
    assert failed["exception"] is not None
    assert not isinstance(failed["exception"], WorkflowActionDispatchError)


@pytest.mark.django_db
def test_a_failed_external_action_still_sends(data_fixture):
    user = data_fixture.create_user()
    table, button_field, row = _button(data_fixture, user)
    action = _add_http_action(data_fixture, button_field)

    with _received(workflow_action_dispatched) as calls:
        with mock_advocate_request(
            raise_exception=request_exceptions.ConnectionError("nope")
        ):
            with pytest.raises(WorkflowActionDispatchError):
                DatabaseWorkflowActionService().dispatch_workflow_actions(
                    user, button_field, row
                )

    assert len(calls) == 1
    assert calls[0]["workflow_action"].id == action.id
    assert calls[0]["result"] is None
    assert calls[0]["exception"] is not None


@pytest.mark.django_db
def test_a_button_with_only_client_actions_sends_nothing_per_action(data_fixture):
    user = data_fixture.create_user()
    table, button_field, row = _button(data_fixture, user)
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )

    with _received(workflow_action_dispatched) as calls:
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    assert calls == []


def _click(api_client, token, button_field, row_id):
    return api_client.post(
        reverse(
            "api:database:workflow_actions:dispatch",
            kwargs={"field_id": button_field.id},
        ),
        {"row_id": row_id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


@pytest.mark.django_db
def test_a_completed_click_sends_its_outcome(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    action = _add_row_action(data_fixture, button_field, table)

    with _received(button_field_dispatched) as calls:
        response = _click(api_client, token, button_field, row.id)

    assert response.status_code == HTTP_200_OK
    assert len(calls) == 1
    call = calls[0]
    assert call["outcome"] == DispatchOutcome.COMPLETED
    assert call["failed_position"] is None
    assert call["duration_ms"] > 0
    assert call["field"].id == button_field.id
    assert call["row_id"] == row.id
    assert call["user"] == user
    assert [wa.id for wa in call["workflow_actions"]] == [action.id]


@pytest.mark.django_db
def test_a_failed_click_sends_the_failing_position(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_row_action(data_fixture, button_field, table)
    data_fixture.create_database_workflow_action(
        LocalBaserowDeleteRowWorkflowAction, field=button_field
    )

    with _received(button_field_dispatched) as calls:
        response = _click(api_client, token, button_field, row.id)

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert len(calls) == 1
    assert calls[0]["outcome"] == DispatchOutcome.FAILED
    assert calls[0]["failed_position"] == 2
    assert len(calls[0]["workflow_actions"]) == 2


@pytest.mark.django_db
def test_a_throttled_click_sends_throttled(api_client, data_fixture, settings):
    settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS = (
        RateLimit(period_in_seconds=60, number_of_calls=1),
    )
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    action = _add_http_action(data_fixture, button_field)

    with _received(button_field_dispatched) as calls:
        with mock_advocate_request({"ok": True}):
            _click(api_client, token, button_field, row.id)
            response = _click(api_client, token, button_field, row.id)

    assert response.status_code == HTTP_429_TOO_MANY_REQUESTS
    assert [call["outcome"] for call in calls] == [
        DispatchOutcome.COMPLETED,
        DispatchOutcome.THROTTLED,
    ]
    # The snapshot is read before the budget, so the refusal still knows what
    # the button carries.
    assert [wa.id for wa in calls[1]["workflow_actions"]] == [action.id]


@pytest.mark.django_db
def test_a_click_on_a_running_sequence_sends_in_progress(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_row_action(data_fixture, button_field, table)
    cache.add(f"button_dispatch_{button_field.id}_{row.id}", True, timeout=30)

    with _received(button_field_dispatched) as calls:
        response = _click(api_client, token, button_field, row.id)

    assert response.status_code == HTTP_409_CONFLICT
    assert [call["outcome"] for call in calls] == [DispatchOutcome.IN_PROGRESS]


@pytest.mark.django_db
def test_a_click_on_a_deactivated_type_sends_deactivated(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    action = _add_row_action(data_fixture, button_field, table)

    with patch.object(type(action.get_type()), "is_deactivated", return_value=True):
        with _received(button_field_dispatched) as calls:
            response = _click(api_client, token, button_field, row.id)

    assert response.status_code == HTTP_403_FORBIDDEN
    assert [call["outcome"] for call in calls] == [DispatchOutcome.DEACTIVATED]


@pytest.mark.django_db
def test_an_outsiders_click_sends_denied_without_a_snapshot(api_client, data_fixture):
    owner = data_fixture.create_user()
    _, outsider_token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, owner)
    _add_row_action(data_fixture, button_field, table)

    with _received(button_field_dispatched) as calls:
        response = _click(api_client, outsider_token, button_field, row.id)

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert len(calls) == 1
    assert calls[0]["outcome"] == DispatchOutcome.DENIED
    assert calls[0]["workflow_actions"] == []


@pytest.mark.django_db
def test_an_unexpected_failure_sends_error(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_row_action(data_fixture, button_field, table)

    with patch.object(
        DatabaseWorkflowActionService,
        "dispatch_workflow_actions",
        side_effect=RuntimeError("boom"),
    ):
        with _received(button_field_dispatched) as calls:
            with pytest.raises(RuntimeError):
                _click(api_client, token, button_field, row.id)

    assert [call["outcome"] for call in calls] == [DispatchOutcome.ERROR]


@pytest.mark.django_db
def test_a_click_on_a_missing_field_sends_nothing(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    field_id = button_field.id
    button_field.delete()
    button_field.id = field_id

    with _received(button_field_dispatched) as calls:
        _click(api_client, token, button_field, row.id)

    assert calls == []


@pytest.mark.django_db
def test_before_dispatch_is_sent_with_the_server_actions(data_fixture):
    user = data_fixture.create_user()
    table, button_field, row = _button(data_fixture, user)
    first = _add_row_action(data_fixture, button_field, table)
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )

    with _received(button_field_before_dispatch) as calls:
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    assert len(calls) == 1
    assert calls[0]["user"] == user
    assert calls[0]["field"] == button_field
    assert [wa.id for wa in calls[0]["workflow_actions"]] == [first.id]


@pytest.mark.django_db
def test_before_dispatch_is_not_sent_for_a_frontend_only_button(data_fixture):
    user = data_fixture.create_user()
    table, button_field, row = _button(data_fixture, user)
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )

    with _received(button_field_before_dispatch) as calls:
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    assert calls == []


class _Refused(Exception):
    pass


@pytest.mark.django_db
def test_a_refusing_receiver_leaves_no_lock_and_no_audit_entry(data_fixture):
    user = data_fixture.create_user()
    table, button_field, row = _button(data_fixture, user)
    _add_row_action(data_fixture, button_field, table)
    audited = []

    def audit(sender, action_type, **kwargs):
        if action_type is DispatchButtonFieldActionType:
            audited.append(kwargs)

    def refuse(sender, **kwargs):
        raise _Refused()

    action_done.connect(audit)
    button_field_before_dispatch.connect(refuse)
    try:
        with pytest.raises(_Refused):
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )
    finally:
        button_field_before_dispatch.disconnect(refuse)
        action_done.disconnect(audit)

    assert audited == []
    assert cache.get(f"button_dispatch_{button_field.id}_{row.id}") is None
    assert table.get_model().objects.count() == 1


def _raise(sender, **kwargs):
    raise RuntimeError("boom")


@pytest.mark.django_db
def test_a_raising_button_field_dispatched_receiver_does_not_break_the_click(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_row_action(data_fixture, button_field, table)

    button_field_dispatched.connect(_raise)
    try:
        response = _click(api_client, token, button_field, row.id)
    finally:
        button_field_dispatched.disconnect(_raise)

    assert response.status_code == HTTP_200_OK
    assert table.get_model().objects.count() == 2


@pytest.mark.django_db
def test_a_raising_workflow_action_dispatched_receiver_does_not_break_the_click(
    data_fixture,
):
    user = data_fixture.create_user()
    table, button_field, row = _button(data_fixture, user)
    _add_row_action(data_fixture, button_field, table, "first")
    _add_row_action(data_fixture, button_field, table, "second")

    workflow_action_dispatched.connect(_raise)
    try:
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )
    finally:
        workflow_action_dispatched.disconnect(_raise)

    assert table.get_model().objects.count() == 3


@pytest.mark.django_db
def test_a_raising_button_field_dispatched_receiver_still_reports_a_failed_click(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_row_action(data_fixture, button_field, table)
    data_fixture.create_database_workflow_action(
        LocalBaserowDeleteRowWorkflowAction, field=button_field
    )

    button_field_dispatched.connect(_raise)
    try:
        response = _click(api_client, token, button_field, row.id)
    finally:
        button_field_dispatched.disconnect(_raise)

    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_a_raising_receiver_never_leaks_its_exception_message(data_fixture, caplog):
    user = data_fixture.create_user()
    table, button_field, row = _button(data_fixture, user)
    _add_row_action(data_fixture, button_field, table)

    def leaky(sender, **kwargs):
        raise RuntimeError("https://secret.example/?key=1")

    workflow_action_dispatched.connect(leaky)
    try:
        with caplog.at_level(logging.ERROR):
            with patch(
                "baserow.contrib.database.workflow_actions.signals.logger"
            ) as mock_logger:
                DatabaseWorkflowActionService().dispatch_workflow_actions(
                    user, button_field, row
                )
    finally:
        workflow_action_dispatched.disconnect(leaky)

    for record in caplog.records:
        assert "secret.example" not in record.getMessage()
        assert "secret.example" not in (record.exc_text or "")
        assert record.name != "django.dispatch"

    mock_logger.error.assert_called_once()
    args, kwargs = mock_logger.error.call_args
    assert kwargs.get("exception") == "RuntimeError"
    for value in list(args) + list(kwargs.values()):
        assert "secret" not in str(value)


class _PluginRefusal(APIException):
    status_code = 403


@pytest.mark.django_db
def test_a_plugin_refusal_with_a_403_sends_denied(api_client, data_fixture, settings):
    settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS = (
        RateLimit(period_in_seconds=60, number_of_calls=1),
    )
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)

    def refuse(sender, **kwargs):
        raise _PluginRefusal()

    button_field_before_dispatch.connect(refuse)
    try:
        with _received(button_field_dispatched) as calls:
            response = _click(api_client, token, button_field, row.id)
    finally:
        button_field_before_dispatch.disconnect(refuse)

    assert response.status_code == HTTP_403_FORBIDDEN
    assert len(calls) == 1
    assert calls[0]["outcome"] == DispatchOutcome.DENIED
    assert cache.get(f"button_dispatch_{button_field.id}_{row.id}") is None

    # The refusal must not have spent the rate limit's only slot.
    with mock_advocate_request({"ok": True}):
        second_response = _click(api_client, token, button_field, row.id)

    assert second_response.status_code == HTTP_200_OK
