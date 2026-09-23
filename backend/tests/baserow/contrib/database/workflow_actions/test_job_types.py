from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from rest_framework.exceptions import ValidationError

from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.actions import (
    DispatchButtonFieldActionType,
)
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
from baserow.core.action.signals import action_done
from baserow.core.jobs.constants import JOB_FAILED, JOB_FINISHED
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.handler import JobHandler
from tests.baserow.contrib.database.workflow_actions.test_sample_data_capture import (
    mock_advocate_request,
)


@pytest.fixture
def audited_clicks():
    """The `action_params` and workspace of every button click registration."""

    received = []

    def receiver(sender, action_type, action_params, workspace, **kwargs):
        if action_type is DispatchButtonFieldActionType:
            received.append((action_params, workspace))

    action_done.connect(receiver)
    yield received
    action_done.disconnect(receiver)


@pytest.fixture
def dispatched_clicks():
    """Every `button_field_dispatched` event sent during the test."""

    received = []

    def receiver(sender, **kwargs):
        received.append(kwargs)

    button_field_dispatched.connect(receiver)
    yield received
    button_field_dispatched.disconnect(receiver)


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
    data_fixture.create_database_workflow_action(
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
def test_the_job_reports_the_click_with_its_outcome(
    data_fixture, dispatched_clicks, audited_clicks
):
    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)

    with mock_advocate_request({"ok": True}):
        _run(user, button_field, row)

    assert len(dispatched_clicks) == 1
    assert dispatched_clicks[0]["outcome"] == DispatchOutcome.COMPLETED
    assert dispatched_clicks[0]["field"] == button_field
    assert dispatched_clicks[0]["row_id"] == row.id
    assert dispatched_clicks[0]["duration_ms"] > 0
    # `DispatchButtonFieldActionType` is not undoable (ADR 006 section 8), so
    # no `Action` row is written for the click, but `dispatch_button_field`
    # still fires `action_done` for the audit log, as the inline path does.
    assert len(audited_clicks) == 1
    params, workspace = audited_clicks[0]
    assert workspace == table.database.workspace
    assert params["field_id"] == button_field.id
    assert params["row_id"] == row.id


@pytest.mark.django_db
def test_a_deleted_row_fails_the_job_with_a_readable_message(data_fixture):
    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)
    row_id = row.id
    row.delete()

    # A race between enqueue and run: the row was deleted while the job
    # waited on the queue.
    job = _run(user, button_field, SimpleNamespace(id=row_id))

    assert job.state == JOB_FAILED
    assert job.error_code == "RowDoesNotExist"


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
