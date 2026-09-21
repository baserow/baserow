import logging
from contextlib import contextmanager
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.urls import reverse

import pytest
from rest_framework.exceptions import APIException
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_409_CONFLICT,
    HTTP_429_TOO_MANY_REQUESTS,
)

from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionDispatchError,
    WorkflowActionDispatchInProgress,
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
    button_field_dispatched,
    workflow_action_dispatched,
    workflow_actions_before_dispatch,
)
from baserow.contrib.database.workflow_actions.types import DispatchOutcome
from baserow.core.action.models import Action
from baserow.throttling.types import RateLimit
from tests.baserow.contrib.database.workflow_actions.test_sample_data_capture import (
    mock_advocate_request,
)


def _table_with_name(data_fixture, user):
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name="People", fields=[("Name", "text", {})]
    )
    return table, table.field_set.get(name="Name")


def _create_row_action(data_fixture, button_field, table, name_field, value):
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.table = table
    service.save()
    service.field_mappings.create(field=name_field, value=f"'{value}'", enabled=True)
    return action


def _http_action(data_fixture, button_field, url):
    action = data_fixture.create_database_workflow_action(
        CoreHTTPRequestWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.url = url
    service.save()
    return action


@contextmanager
def _answer_requests(raise_exception=None):
    response = Mock()
    response.json.return_value = {"ok": True}
    response.text = '{"ok": true}'
    response.headers = {"Content-Type": "application/json"}
    response.status_code = 200
    with patch(
        "baserow.contrib.integrations.core.service_types.send_http_request"
    ) as mock_request:
        if raise_exception is not None:
            mock_request.side_effect = raise_exception
        else:
            mock_request.return_value = response
        yield mock_request


class _Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, sender, **kwargs):
        self.calls.append(kwargs)


@pytest.mark.django_db
def test_each_server_action_sends_dispatched_with_its_result(data_fixture):
    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    first = _create_row_action(data_fixture, button_field, table, name_field, "a")
    second = _create_row_action(data_fixture, button_field, table, name_field, "b")
    recorder = _Recorder()
    workflow_action_dispatched.connect(recorder)
    try:
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )
    finally:
        workflow_action_dispatched.disconnect(recorder)

    assert [c["workflow_action"].id for c in recorder.calls] == [first.id, second.id]
    assert [c["position"] for c in recorder.calls] == [1, 2]
    assert all(c["succeeded"] for c in recorder.calls)
    assert all(c["result"] is not None for c in recorder.calls)
    assert all(c["duration_ms"] >= 0 for c in recorder.calls)
    assert all(
        c["dispatch_context"].field.id == button_field.id for c in recorder.calls
    )


@pytest.mark.django_db
def test_a_failed_action_sends_dispatched_as_not_succeeded(data_fixture):
    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    failing = data_fixture.create_database_workflow_action(
        LocalBaserowDeleteRowWorkflowAction, field=button_field
    )
    recorder = _Recorder()
    workflow_action_dispatched.connect(recorder)
    try:
        with pytest.raises(WorkflowActionDispatchError):
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )
    finally:
        workflow_action_dispatched.disconnect(recorder)

    assert len(recorder.calls) == 1
    assert recorder.calls[0]["workflow_action"].id == failing.id
    assert recorder.calls[0]["succeeded"] is False
    assert recorder.calls[0]["result"] is None
    assert "exception" not in recorder.calls[0]


@pytest.mark.django_db
def test_before_dispatch_is_sent_with_the_server_actions(data_fixture):
    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field, url="'https://x.test'"
    )
    server = _create_row_action(data_fixture, button_field, table, name_field, "a")
    recorder = _Recorder()
    workflow_actions_before_dispatch.connect(recorder)
    try:
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )
    finally:
        workflow_actions_before_dispatch.disconnect(recorder)

    assert len(recorder.calls) == 1
    assert recorder.calls[0]["user"] == user
    assert recorder.calls[0]["field"].id == button_field.id
    assert [wa.id for wa in recorder.calls[0]["workflow_actions"]] == [server.id]


@pytest.mark.django_db
def test_before_dispatch_is_not_sent_for_a_frontend_only_button(data_fixture):
    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field, url="'https://x.test'"
    )
    recorder = _Recorder()
    workflow_actions_before_dispatch.connect(recorder)
    try:
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )
    finally:
        workflow_actions_before_dispatch.disconnect(recorder)

    assert recorder.calls == []


@pytest.mark.django_db
def test_a_refusing_before_dispatch_receiver_leaves_no_lock_and_no_action(
    data_fixture,
):
    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    _create_row_action(data_fixture, button_field, table, name_field, "a")

    class Refused(Exception):
        pass

    def refuse(sender, **kwargs):
        raise Refused()

    workflow_actions_before_dispatch.connect(refuse)
    try:
        with pytest.raises(Refused):
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )
    finally:
        workflow_actions_before_dispatch.disconnect(refuse)

    assert cache.get(f"button_dispatch_{button_field.id}_{row.id}") is None
    assert table.get_model().objects.exclude(id=row.id).count() == 0
    assert not Action.objects.filter(type="dispatch_button_field").exists()


@pytest.mark.django_db
def test_a_failing_callable_object_receiver_does_not_fail_the_click(data_fixture):
    # `send_robust` logs a failing receiver first, and that log reads
    # `__qualname__`, which an instance has not.
    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = _create_row_action(data_fixture, button_field, table, name_field, "a")

    class _Failing:
        def __call__(self, sender, **kwargs):
            raise RuntimeError("bookkeeping receiver blew up")

    failing = _Failing()
    workflow_action_dispatched.connect(failing)
    try:
        result = DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )
    finally:
        workflow_action_dispatched.disconnect(failing)

    assert [d.workflow_action.id for d in result.dispatched] == [action.id]
    assert table.get_model().objects.exclude(id=row.id).count() == 1


@pytest.mark.django_db
def test_a_receiver_that_returns_a_value_is_not_reported_as_failed(data_fixture):
    # `send_robust` answers with what each receiver returned, and only
    # substitutes the exception for the ones that raised.
    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    _create_row_action(data_fixture, button_field, table, name_field, "a")

    def charge(sender, **kwargs):
        return {"units": 1}

    workflow_action_dispatched.connect(charge)
    try:
        with patch(
            "baserow.contrib.database.workflow_actions.service.logger"
        ) as mock_logger:
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )
    finally:
        workflow_action_dispatched.disconnect(charge)

    # `opt` too: a `logger.opt(...)` report never reaches `error` on the mock.
    mock_logger.error.assert_not_called()
    mock_logger.opt.assert_not_called()


@pytest.mark.django_db
def test_a_failing_receiver_on_the_first_action_leaves_the_rest_running(data_fixture):
    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    first = _create_row_action(data_fixture, button_field, table, name_field, "a")
    second = _create_row_action(data_fixture, button_field, table, name_field, "b")

    def fail_on_the_first(sender, workflow_action, **kwargs):
        if workflow_action.id == first.id:
            raise RuntimeError("bookkeeping receiver blew up")

    workflow_action_dispatched.connect(fail_on_the_first)
    try:
        result = DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )
    finally:
        workflow_action_dispatched.disconnect(fail_on_the_first)

    assert [d.workflow_action.id for d in result.dispatched] == [first.id, second.id]
    assert table.get_model().objects.exclude(id=row.id).count() == 2


@pytest.mark.django_db
def test_the_actions_a_before_dispatch_receiver_sees_cannot_change_the_click(
    data_fixture,
):
    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = _create_row_action(data_fixture, button_field, table, name_field, "a")

    def empty_them(sender, workflow_actions, **kwargs):
        # On a list this would send the click down the frontend-only branch.
        with pytest.raises(TypeError):
            workflow_actions[:] = []

    workflow_actions_before_dispatch.connect(empty_them)
    try:
        result = DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )
    finally:
        workflow_actions_before_dispatch.disconnect(empty_them)

    assert [d.workflow_action.id for d in result.dispatched] == [action.id]
    assert table.get_model().objects.exclude(id=row.id).count() == 1


@pytest.mark.django_db
def test_a_failing_dispatched_receiver_does_not_fail_the_click(data_fixture):
    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = _create_row_action(data_fixture, button_field, table, name_field, "a")

    def fail(sender, **kwargs):
        raise RuntimeError("bookkeeping receiver blew up")

    workflow_action_dispatched.connect(fail)
    try:
        result = DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )
    finally:
        workflow_action_dispatched.disconnect(fail)

    assert [d.workflow_action.id for d in result.dispatched] == [action.id]
    assert table.get_model().objects.exclude(id=row.id).count() == 1


@pytest.mark.django_db
def test_before_dispatch_is_not_sent_for_a_click_refused_as_already_running(
    data_fixture,
):
    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    _create_row_action(data_fixture, button_field, table, name_field, "a")
    recorder = _Recorder()
    held = cache.lock(f"button_dispatch_{button_field.id}_{row.id}", timeout=30)
    assert held.acquire(blocking=False)
    workflow_actions_before_dispatch.connect(recorder)
    try:
        with pytest.raises(WorkflowActionDispatchInProgress):
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )
    finally:
        workflow_actions_before_dispatch.disconnect(recorder)
        held.release()

    assert recorder.calls == []


@pytest.mark.django_db
def test_an_external_action_sends_both_signals(data_fixture):
    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = _http_action(data_fixture, button_field, "'http://example.notexist/'")
    before = _Recorder()
    dispatched = _Recorder()
    workflow_actions_before_dispatch.connect(before)
    workflow_action_dispatched.connect(dispatched)
    try:
        with _answer_requests():
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )
    finally:
        workflow_actions_before_dispatch.disconnect(before)
        workflow_action_dispatched.disconnect(dispatched)

    assert [wa.id for wa in before.calls[0]["workflow_actions"]] == [action.id]
    assert len(dispatched.calls) == 1
    assert dispatched.calls[0]["workflow_action"].id == action.id
    assert dispatched.calls[0]["succeeded"] is True
    assert dispatched.calls[0]["position"] == 1


@pytest.mark.django_db
def test_a_failing_receiver_does_not_log_the_address_a_failed_action_reached(
    data_fixture, caplog
):
    # A receiver's failure raised while the dispatch failure was being handled
    # would chain it, and Django logs the receiver's failure with its traceback.
    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    _http_action(data_fixture, button_field, "'http://example.notexist/p?token=canary'")
    dispatched = _Recorder()

    def fail(sender, **kwargs):
        raise RuntimeError("bookkeeping receiver blew up")

    workflow_action_dispatched.connect(fail)
    workflow_action_dispatched.connect(dispatched)
    try:
        with caplog.at_level(logging.ERROR, logger="django.dispatch"):
            # The builtin one: the service turns it into a failure that names
            # the URL.
            with _answer_requests(raise_exception=ConnectionError("refused")):
                with pytest.raises(WorkflowActionDispatchError):
                    DatabaseWorkflowActionService().dispatch_workflow_actions(
                        user, button_field, row
                    )
    finally:
        workflow_action_dispatched.disconnect(fail)
        workflow_action_dispatched.disconnect(dispatched)

    assert dispatched.calls[0]["succeeded"] is False
    assert "bookkeeping receiver blew up" in caplog.text
    assert "canary" not in caplog.text


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
def test_a_raising_button_field_dispatched_receiver_never_leaks_its_message(
    api_client, data_fixture, caplog
):
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_row_action(data_fixture, button_field, table)

    def leaky(sender, **kwargs):
        raise RuntimeError("https://secret.example/?key=1")

    button_field_dispatched.connect(leaky)
    try:
        with caplog.at_level(logging.ERROR):
            with patch(
                "baserow.contrib.database.workflow_actions.signals.logger"
            ) as mock_logger:
                _click(api_client, token, button_field, row.id)
    finally:
        button_field_dispatched.disconnect(leaky)

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

    workflow_actions_before_dispatch.connect(refuse)
    try:
        with _received(button_field_dispatched) as calls:
            response = _click(api_client, token, button_field, row.id)
    finally:
        workflow_actions_before_dispatch.disconnect(refuse)

    assert response.status_code == HTTP_403_FORBIDDEN
    assert len(calls) == 1
    assert calls[0]["outcome"] == DispatchOutcome.DENIED
    assert cache.get(f"button_dispatch_{button_field.id}_{row.id}") is None

    # The refusal must not have spent the rate limit's only slot.
    with mock_advocate_request({"ok": True}):
        second_response = _click(api_client, token, button_field, row.id)

    assert second_response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_a_plugin_refusal_with_djangos_permission_denied_sends_denied(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_row_action(data_fixture, button_field, table)

    def refuse(sender, **kwargs):
        raise DjangoPermissionDenied()

    workflow_actions_before_dispatch.connect(refuse)
    try:
        with _received(button_field_dispatched) as calls:
            response = _click(api_client, token, button_field, row.id)
    finally:
        workflow_actions_before_dispatch.disconnect(refuse)

    assert response.status_code == HTTP_403_FORBIDDEN
    assert [call["outcome"] for call in calls] == [DispatchOutcome.DENIED]
