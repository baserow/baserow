import logging
from contextlib import contextmanager
from unittest.mock import Mock, patch

from django.core.cache import cache

import pytest

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
    workflow_action_dispatched,
    workflow_actions_before_dispatch,
)
from baserow.core.action.models import Action


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
