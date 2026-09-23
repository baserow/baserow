from contextlib import nullcontext
from unittest.mock import patch

import pytest
from rest_framework.exceptions import ValidationError

from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.job_types import (
    ButtonFieldDispatchJobType,
)
from baserow.contrib.database.workflow_actions.models import (
    CoreHTTPRequestWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    OpenUrlWorkflowAction,
)
from baserow.contrib.database.workflow_actions.signals import button_field_dispatched
from baserow.contrib.database.workflow_actions.types import DispatchOutcome
from baserow.core.action.models import Action
from baserow.core.jobs.constants import JOB_FAILED, JOB_FINISHED
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.handler import JobHandler
from tests.baserow.contrib.database.workflow_actions.test_sample_data_capture import (
    mock_advocate_request,
)


def _button(data_fixture, user):
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name="People", fields=[("Name", "text", {})]
    )
    name_field = table.field_set.get(name="Name")
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    return table, name_field, button_field, row


def _add_row_action(data_fixture, button_field, table, name_field, value):
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.table = table
    service.save()
    service.field_mappings.create(field=name_field, value=f"'{value}'", enabled=True)
    return action


def _add_http_action(data_fixture, button_field):
    action = data_fixture.create_database_workflow_action(
        CoreHTTPRequestWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.url = "'http://example.notexist/'"
    service.save()
    return action


def _run(user, button_field, row):
    job = JobHandler().create_and_start_job(
        user,
        ButtonFieldDispatchJobType.type,
        sync=True,
        field=button_field,
        row_id=row.id,
    )
    job.refresh_from_db()
    return job


@pytest.mark.django_db
def test_a_finished_job_carries_the_results_and_client_actions(data_fixture):
    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    http_action = _add_http_action(data_fixture, button_field)
    open_url = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )

    with mock_advocate_request({"ok": True}):
        job = _run(user, button_field, row)

    assert job.state == JOB_FINISHED
    assert [r["workflow_action_id"] for r in job.results] == [http_action.id]
    assert job.results[0]["position"] == 1
    assert job.results[0]["status"] == "completed"
    assert [a["id"] for a in job.client_actions] == [open_url.id]
    assert job.client_actions[0]["position"] == 2


@pytest.mark.django_db
def test_a_failing_action_keeps_what_ran_and_names_the_failure(data_fixture):
    """ADR 006 section 3: the job runs outside a transaction."""

    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_row_action(data_fixture, button_field, table, name_field, "first")
    _add_row_action(data_fixture, button_field, table, name_field, "second")
    _add_http_action(data_fixture, button_field)
    # A delete-row action with no table configured passes the pre-check (its
    # `raise_if_misconfigured` is a no-op) and fails once dispatched.
    broken = data_fixture.create_database_workflow_action(
        LocalBaserowDeleteRowWorkflowAction, field=button_field
    )

    with mock_advocate_request({"ok": True}):
        job = _run(user, button_field, row)

    assert job.state == JOB_FAILED
    assert job.human_readable_error == (
        "Actions 1, 2 and 3 ran before action 4 failed: No table selected"
    )
    assert job.error_code == "WorkflowActionDispatchError"
    created = [
        getattr(r, f"field_{name_field.id}")
        for r in table.get_model().objects.exclude(id=row.id).order_by("id")
    ]
    assert created == ["first", "second"]


@pytest.mark.django_db
def test_the_job_type_runs_outside_a_transaction():
    job_type = ButtonFieldDispatchJobType()
    assert isinstance(job_type.transaction_atomic_context(None), nullcontext)


@pytest.mark.django_db
def test_a_sixth_click_in_flight_is_refused(data_fixture):
    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)

    with patch("baserow.core.jobs.handler.run_async_job"):
        for _ in range(5):
            JobHandler().create_and_start_job(
                user, ButtonFieldDispatchJobType.type, field=button_field, row_id=row.id
            )
        with pytest.raises(MaxJobCountExceeded):
            JobHandler().create_and_start_job(
                user, ButtonFieldDispatchJobType.type, field=button_field, row_id=row.id
            )


@pytest.mark.django_db
def test_the_job_cannot_be_started_without_a_field(data_fixture):
    user = data_fixture.create_user()

    with pytest.raises(ValidationError):
        JobHandler().create_and_start_job(user, ButtonFieldDispatchJobType.type)


@pytest.mark.django_db
def test_the_job_reports_the_click_with_its_outcome(data_fixture):
    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)
    received = []

    def _record(sender, **kwargs):
        received.append(kwargs)

    # A reference is kept on `_record`: `connect` holds only a weak reference,
    # so an inline lambda with nothing else pointing at it is garbage
    # collected before the signal is sent.
    button_field_dispatched.connect(_record)

    with mock_advocate_request({"ok": True}):
        _run(user, button_field, row)

    assert len(received) == 1
    assert received[0]["outcome"] == DispatchOutcome.COMPLETED
    assert received[0]["field"] == button_field
    assert received[0]["row_id"] == row.id
    assert received[0]["duration_ms"] > 0
    # `DispatchButtonFieldActionType` is not undoable (ADR 006 section 8), so
    # neither the inline path nor the job writes an `Action` row for the
    # click itself; `dispatch_button_field` only fires `action_done` for
    # webhooks and realtime updates to observe.
    assert Action.objects.filter(user=user).count() == 0


@pytest.mark.django_db
def test_the_job_restores_the_clickers_websocket_id(data_fixture):
    user = data_fixture.create_user()
    user.web_socket_id = "socket-1"
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)
    seen = {}

    def spy(self, user, field, row, **kwargs):
        seen["web_socket_id"] = getattr(user, "web_socket_id", None)
        return original(self, user, field, row, **kwargs)

    from baserow.contrib.database.workflow_actions.service import (
        DatabaseWorkflowActionService,
    )

    original = DatabaseWorkflowActionService.dispatch_workflow_actions
    with (
        mock_advocate_request({"ok": True}),
        patch.object(DatabaseWorkflowActionService, "dispatch_workflow_actions", spy),
    ):
        _run(user, button_field, row)

    assert seen["web_socket_id"] == "socket-1"
