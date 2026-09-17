from contextlib import contextmanager

import pytest
from requests import exceptions as request_exceptions

from baserow.contrib.database.table.handler import TableHandler
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
    workflow_action_dispatched,
)
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
