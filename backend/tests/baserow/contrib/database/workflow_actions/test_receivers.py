from unittest.mock import call, patch

from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.api.sessions import set_untrusted_client_session_id
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.models import (
    CoreHTTPRequestWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
    OpenUrlWorkflowAction,
)
from baserow.contrib.database.workflow_actions.receivers import (
    capture_button_field_dispatched,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.contrib.database.workflow_actions.telemetry import (
    record_button_field_dispatched,
    record_workflow_action_dispatched,
)
from baserow.contrib.database.workflow_actions.types import DispatchOutcome
from baserow.core.services.types import DispatchResult

POSTHOG_PROPERTIES = {
    "database_id",
    "table_id",
    "field_id",
    "outcome",
    "failed_position",
    "duration_ms",
    "action_types",
    "server_action_count",
    "client_action_count",
    "external_action_count",
}


def _button_with_three_actions(data_fixture, user):
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name="People", fields=[("Name", "text", {})]
    )
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    create_row = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = create_row.service.specific
    service.table = table
    service.save()
    http = data_fixture.create_database_workflow_action(
        CoreHTTPRequestWorkflowAction, field=button_field
    )
    open_url = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )
    return table, button_field, row, [create_row, http, open_url]


@pytest.mark.django_db
@patch("baserow.contrib.database.workflow_actions.receivers.capture_user_event")
def test_the_posthog_event_carries_the_documented_properties(
    mock_capture, data_fixture
):
    user = data_fixture.create_user()
    set_untrusted_client_session_id(user, "session-1")
    table, button_field, _, workflow_actions = _button_with_three_actions(
        data_fixture, user
    )

    capture_button_field_dispatched(
        sender=None,
        user=user,
        field=button_field,
        row_id=123,
        workflow_actions=workflow_actions,
        outcome=DispatchOutcome.FAILED,
        failed_position=2,
        duration_ms=12.6,
    )

    mock_capture.assert_called_once()
    args, kwargs = mock_capture.call_args
    assert args[0] == user
    assert args[1] == "button_field_dispatched"
    properties = args[2]
    assert set(properties) == POSTHOG_PROPERTIES
    assert properties == {
        "database_id": table.database_id,
        "table_id": table.id,
        "field_id": button_field.id,
        "outcome": "failed",
        "failed_position": 2,
        "duration_ms": 13,
        "action_types": ["local_baserow_create_row", "http_request", "open_url"],
        "server_action_count": 2,
        "client_action_count": 1,
        "external_action_count": 1,
    }
    assert kwargs["workspace"] == table.database.workspace
    assert kwargs["session"] == "session-1"


@pytest.mark.django_db
@patch("baserow.contrib.database.workflow_actions.receivers.capture_user_event")
def test_a_click_through_the_api_captures_one_event(
    mock_capture, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )

    response = api_client.post(
        reverse(
            "api:database:workflow_actions:dispatch",
            kwargs={"field_id": button_field.id},
        ),
        {"row_id": row.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert [mock_call.args[1] for mock_call in mock_capture.call_args_list] == [
        "button_field_dispatched"
    ]


@pytest.mark.django_db
@patch("baserow.core.posthog.capture_user_event")
def test_the_audit_log_click_is_not_sent_to_posthog(mock_capture, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )

    DatabaseWorkflowActionService().dispatch_workflow_actions(user, button_field, row)

    assert "dispatch_button_field" not in [
        mock_call.args[1] for mock_call in mock_capture.call_args_list
    ]


TELEMETRY = "baserow.contrib.database.workflow_actions.telemetry"


@patch(f"{TELEMETRY}.button_field_dispatch_duration")
@patch(f"{TELEMETRY}.button_field_dispatch_counter")
def test_a_click_adds_to_the_click_metrics(counter, duration):
    record_button_field_dispatched(
        sender=None,
        user=None,
        field=None,
        row_id=1,
        workflow_actions=[],
        outcome=DispatchOutcome.THROTTLED,
        failed_position=None,
        duration_ms=4.5,
    )

    counter.add.assert_called_once_with(1, {"outcome": "throttled"})
    duration.record.assert_called_once_with(4.5, {"outcome": "throttled"})


class _FakeType:
    type = "http_request"


class _FakeAction:
    def get_type(self):
        return _FakeType()


@patch(f"{TELEMETRY}.workflow_action_dispatch_duration")
@patch(f"{TELEMETRY}.workflow_action_dispatch_counter")
def test_an_action_adds_to_the_action_metrics(counter, duration):
    record_workflow_action_dispatched(
        sender=None,
        workflow_action=_FakeAction(),
        dispatch_context=None,
        position=1,
        succeeded=True,
        result=DispatchResult(),
        duration_ms=10.0,
    )
    record_workflow_action_dispatched(
        sender=None,
        workflow_action=_FakeAction(),
        dispatch_context=None,
        position=2,
        succeeded=True,
        result=DispatchResult(status=504),
        duration_ms=30.0,
    )
    record_workflow_action_dispatched(
        sender=None,
        workflow_action=_FakeAction(),
        dispatch_context=None,
        position=3,
        succeeded=False,
        result=None,
        duration_ms=20.0,
    )

    assert counter.add.call_args_list == [
        call(1, {"action_type": "http_request", "result": "ok"}),
        call(1, {"action_type": "http_request", "result": "error_status"}),
        call(1, {"action_type": "http_request", "result": "failed"}),
    ]
    assert duration.record.call_args_list == [
        call(10.0, {"action_type": "http_request", "result": "ok"}),
        call(30.0, {"action_type": "http_request", "result": "error_status"}),
        call(20.0, {"action_type": "http_request", "result": "failed"}),
    ]


@pytest.mark.django_db
@patch("baserow.contrib.database.workflow_actions.receivers.capture_user_event")
@patch(f"{TELEMETRY}.workflow_action_dispatch_counter")
@patch(f"{TELEMETRY}.button_field_dispatch_counter")
def test_the_metric_receivers_are_connected(
    click_counter, action_counter, mock_capture, data_fixture
):
    from baserow.contrib.database.workflow_actions.signals import (
        button_field_dispatched,
        workflow_action_dispatched,
    )

    button_field = data_fixture.create_button_field()
    button_field_dispatched.send(
        None,
        user=None,
        field=button_field,
        row_id=1,
        workflow_actions=[],
        outcome=DispatchOutcome.COMPLETED,
        failed_position=None,
        duration_ms=1.0,
    )
    workflow_action_dispatched.send(
        None,
        workflow_action=_FakeAction(),
        dispatch_context=None,
        position=1,
        succeeded=True,
        result=DispatchResult(),
        duration_ms=1.0,
    )

    click_counter.add.assert_called_once()
    action_counter.add.assert_called_once()
