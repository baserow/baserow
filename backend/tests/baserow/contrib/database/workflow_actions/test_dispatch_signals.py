from django.core.cache import cache

import pytest

from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionDispatchError,
)
from baserow.contrib.database.workflow_actions.models import (
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    OpenUrlWorkflowAction,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.contrib.database.workflow_actions.signals import (
    button_field_before_dispatch,
    workflow_action_dispatched,
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
    assert all(c["exception"] is None for c in recorder.calls)
    assert all(c["result"] is not None for c in recorder.calls)
    assert all(c["duration_ms"] >= 0 for c in recorder.calls)
    assert all(c["dispatch_context"] is not None for c in recorder.calls)
    assert all(c["field"].id == button_field.id for c in recorder.calls)


@pytest.mark.django_db
def test_a_failed_action_sends_dispatched_with_the_exception(data_fixture):
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
    assert recorder.calls[0]["result"] is None
    assert isinstance(recorder.calls[0]["exception"], Exception)


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
    button_field_before_dispatch.connect(recorder)
    try:
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )
    finally:
        button_field_before_dispatch.disconnect(recorder)

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
    button_field_before_dispatch.connect(recorder)
    try:
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )
    finally:
        button_field_before_dispatch.disconnect(recorder)

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

    button_field_before_dispatch.connect(refuse)
    try:
        with pytest.raises(Refused):
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )
    finally:
        button_field_before_dispatch.disconnect(refuse)

    assert cache.get(f"button_dispatch_{button_field.id}_{row.id}") is None
    assert table.get_model().objects.exclude(id=row.id).count() == 0
    assert not Action.objects.filter(type="dispatch_button_field").exists()


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
