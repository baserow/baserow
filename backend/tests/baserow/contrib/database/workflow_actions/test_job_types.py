from contextlib import nullcontext
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.db import DataError
from django.utils import timezone

import pytest
from rest_framework.exceptions import APIException, ValidationError

from baserow.api.sessions import (
    get_user_remote_addr_ip,
    set_client_undo_redo_action_group_id,
    set_untrusted_client_session_id,
    set_user_remote_addr_ip,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.actions import (
    DispatchButtonFieldActionType,
)
from baserow.contrib.database.workflow_actions.job_types import (
    ButtonFieldDispatchJobType,
    denied_message,
)
from baserow.contrib.database.workflow_actions.models import (
    ButtonFieldDispatchJob,
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
    workflow_actions_before_dispatch,
)
from baserow.contrib.database.workflow_actions.types import DispatchOutcome
from baserow.core.action.signals import action_done
from baserow.core.exceptions import PermissionException
from baserow.core.jobs.constants import JOB_CANCELLED, JOB_FAILED, JOB_FINISHED
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.tasks import run_async_job
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


def _accepted_ids(button_field):
    service = DatabaseWorkflowActionService()
    return service.accepted_actions(service.get_dispatch_snapshot(button_field))


def _run(user, button_field, row, accepted_actions=None):
    if accepted_actions is None:
        accepted_actions = _accepted_ids(button_field)
    job = JobHandler().create_and_start_job(
        user,
        ButtonFieldDispatchJobType.type,
        sync=True,
        field=button_field,
        row_id=row.id,
        accepted_actions=accepted_actions,
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
def test_an_action_added_after_the_click_fails_the_job_without_running(
    data_fixture, dispatched_clicks
):
    """The request checked and charged the list it accepted. An action added
    while the job waited on the queue has had neither, so nothing runs."""

    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)
    accepted = _accepted_ids(button_field)
    _add_row_action(data_fixture, button_field, table, name_field, "late")

    with mock_advocate_request({"ok": True}) as request:
        job = _run(user, button_field, row, accepted_actions=accepted)

    assert job.state == JOB_FAILED
    assert job.error_code == "WorkflowActionsChangedSinceClick"
    assert job.human_readable_error == (
        "The button's actions changed while the click was waiting. "
        "Click again to run the new ones."
    )
    assert not request.called
    assert table.get_model().objects.exclude(id=row.id).count() == 0
    assert [c["outcome"] for c in dispatched_clicks] == [DispatchOutcome.ERROR]


@pytest.mark.django_db
def test_a_reordered_list_fails_the_job_the_same_way(data_fixture):
    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_row_action(data_fixture, button_field, table, name_field, "first")
    _add_http_action(data_fixture, button_field)
    accepted = _accepted_ids(button_field)

    job = _run(user, button_field, row, accepted_actions=list(reversed(accepted)))

    assert job.state == JOB_FAILED
    assert job.error_code == "WorkflowActionsChangedSinceClick"
    assert table.get_model().objects.exclude(id=row.id).count() == 0


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


class _PluginRefusal(APIException):
    status_code = 403
    default_detail = "Quota exceeded."


@pytest.mark.django_db
def test_a_plugin_refusal_sends_denied_and_fails_the_job(
    data_fixture, dispatched_clicks
):
    """A receiver of `workflow_actions_before_dispatch` refusing the click (a
    SaaS quota, say) is not in `job_exceptions_map` by its own class, since a
    plugin's exception is not one Baserow defines; whenever `outcome_for`
    recognises it as a denial, `run` re-raises it as
    `WorkflowActionDispatchDenied`, so the job fails cleanly with the
    plugin's own message rather than raising out of the task."""

    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)

    def refuse(sender, **kwargs):
        raise _PluginRefusal()

    workflow_actions_before_dispatch.connect(refuse)
    try:
        job = _run(user, button_field, row)
    finally:
        workflow_actions_before_dispatch.disconnect(refuse)

    assert len(dispatched_clicks) == 1
    assert dispatched_clicks[0]["outcome"] == DispatchOutcome.DENIED

    assert job.state == JOB_FAILED
    assert job.human_readable_error == "Quota exceeded."
    assert job.error_code == "WorkflowActionDispatchDenied"


@pytest.mark.django_db
def test_a_plugin_refusal_with_permission_exception_fails_the_job_the_same_way(
    data_fixture, dispatched_clicks
):
    """A plugin need not raise a DRF `APIException`: `PermissionException` and
    Django's `PermissionDenied` are denials too (`outcome_for` recognises
    both), and get the same `WorkflowActionDispatchDenied` failure."""

    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)

    def refuse(sender, **kwargs):
        raise PermissionException()

    workflow_actions_before_dispatch.connect(refuse)
    try:
        job = _run(user, button_field, row)
    finally:
        workflow_actions_before_dispatch.disconnect(refuse)

    assert len(dispatched_clicks) == 1
    assert dispatched_clicks[0]["outcome"] == DispatchOutcome.DENIED

    assert job.state == JOB_FAILED
    assert job.error_code == "WorkflowActionDispatchDenied"
    # Core wording is internal; the clicker gets what the refused request
    # would have said.
    assert job.human_readable_error == (
        "You don't have the required permission to execute this operation."
    )


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
def test_the_job_restores_the_clickers_ip_and_session_for_the_audit_log(
    data_fixture,
):
    """The audit log reads the IP address and PostHog the session id from the
    user, so the job carries both over from the request that clicked."""

    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)
    set_user_remote_addr_ip(user, "203.0.113.7")
    set_untrusted_client_session_id(user, "session-1")
    set_client_undo_redo_action_group_id(user, str(uuid4()))
    audited = []

    def receiver(sender, user, action_type, session, **kwargs):
        if action_type is DispatchButtonFieldActionType:
            audited.append((get_user_remote_addr_ip(user), session))

    action_done.connect(receiver)
    try:
        with mock_advocate_request({"ok": True}):
            job = _run(user, button_field, row)
    finally:
        action_done.disconnect(receiver)

    assert job.state == JOB_FINISHED
    assert job.user_ip_address == "203.0.113.7"
    assert audited == [("203.0.113.7", "session-1")]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_a_click_run_by_the_job_does_not_enter_the_undo_stack(data_fixture):
    """The job restores the clicker's session id, which must still not let the
    click's own row changes into their undo stack (ADR 006 section 8)."""

    from baserow.contrib.database.action.scopes import TableActionScopeType
    from baserow.core.action.handler import ActionHandler

    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_row_action(data_fixture, button_field, table, name_field, "first")
    _add_http_action(data_fixture, button_field)
    set_untrusted_client_session_id(user, "session-1")

    with mock_advocate_request({"ok": True}):
        job = _run(user, button_field, row)

    assert job.state == JOB_FINISHED
    assert job.user_session_id == "session-1"
    undone = ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], "session-1"
    )
    assert undone == []
    assert table.get_model().objects.exclude(id=row.id).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("trash", ["field", "table", "database"])
def test_a_trashed_button_fails_the_job_with_a_readable_message(
    data_fixture, dispatched_clicks, trash
):
    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)

    with patch("baserow.core.jobs.handler.run_async_job"):
        job = JobHandler().create_and_start_job(
            user, ButtonFieldDispatchJobType.type, field=button_field, row_id=row.id
        )
    # Trashed while the job waited on the queue.
    trashed = {"field": button_field, "table": table, "database": table.database}[trash]
    trashed.trashed = True
    trashed.save()

    with mock_advocate_request({"ok": True}) as request:
        run_async_job(job.id)

    job.refresh_from_db()
    assert job.state == JOB_FAILED
    assert job.error_code == "FieldDoesNotExist"
    assert job.human_readable_error == "The button no longer exists."
    assert not request.called
    assert dispatched_clicks == []


@pytest.mark.django_db
def test_a_button_retyped_while_its_click_waits_fails_the_job(
    data_fixture, dispatched_clicks
):
    """Changing the type deletes the button row but keeps the field the job
    points at, so the retype has no job to update and the worker refuses a
    field that is no longer a button."""

    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)

    with patch("baserow.core.jobs.handler.run_async_job"):
        job = JobHandler().create_and_start_job(
            user,
            ButtonFieldDispatchJobType.type,
            field=button_field,
            row_id=row.id,
            accepted_actions=_accepted_ids(button_field),
        )
    FieldHandler().update_field(user, button_field, new_type_name="text")

    with mock_advocate_request({"ok": True}) as request:
        run_async_job(job.id)

    job = ButtonFieldDispatchJob.objects.get(id=job.id)
    assert job.field_id == button_field.id
    assert job.state == JOB_FAILED
    assert job.error_code == "FieldDoesNotExist"
    assert job.human_readable_error == "The button no longer exists."
    assert not request.called
    assert dispatched_clicks == []


@pytest.mark.django_db
def test_an_action_retyped_to_external_after_the_click_fails_the_job(data_fixture):
    """A retype keeps the id, so the ids alone would not tell. The click was
    charged for one external action and must not send two."""

    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    row_action = _add_row_action(data_fixture, button_field, table, name_field, "a")
    _add_http_action(data_fixture, button_field)
    accepted = _accepted_ids(button_field)
    DatabaseWorkflowActionService().update_workflow_action(
        user, row_action, type="http_request"
    )

    with mock_advocate_request({"ok": True}) as request:
        job = _run(user, button_field, row, accepted_actions=accepted)

    assert job.state == JOB_FAILED
    assert job.error_code == "WorkflowActionsChangedSinceClick"
    assert not request.called


@pytest.mark.django_db
def test_a_click_older_than_the_job_cleanup_does_not_run(data_fixture, settings):
    """The cleanup fails a job this old and frees its cell, so a retry may
    already have sent the same request. Consumed late, it must not send it
    again."""

    settings.BASEROW_JOB_SOFT_TIME_LIMIT = 1800
    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)

    with patch("baserow.core.jobs.handler.run_async_job"):
        job = JobHandler().create_and_start_job(
            user,
            ButtonFieldDispatchJobType.type,
            field=button_field,
            row_id=row.id,
            accepted_actions=_accepted_ids(button_field),
        )
    ButtonFieldDispatchJob.objects.filter(id=job.id).update(
        created_on=timezone.now() - timedelta(seconds=1801)
    )

    with mock_advocate_request({"ok": True}) as request:
        run_async_job(job.id)

    job.refresh_from_db()
    assert job.state == JOB_FAILED
    assert job.error_code == "WorkflowActionClickExpired"
    assert not request.called


@pytest.mark.django_db
def test_an_answer_postgres_cannot_store_still_finishes_the_click(data_fixture):
    """A NUL character or a lone surrogate in an endpoint's answer was fine in
    an inline response but is refused by a jsonb column."""

    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )

    answer = {"text": "a\x00b", "cut": "cut \ud83d", "emoji": "\U0001f600"}
    with mock_advocate_request({**answer, "ratio": float("nan")}):
        job = _run(user, button_field, row)

    assert job.state == JOB_FINISHED, job.error
    job.refresh_from_db()
    body = job.results[0]["data"]["body"]
    assert body["text"] == "ab"
    assert body["cut"] == "cut "
    assert body["emoji"] == "\U0001f600"
    assert body["ratio"] is None


@pytest.mark.django_db
def test_an_answer_that_cannot_be_saved_still_fails_the_job(data_fixture):
    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)
    original_save = ButtonFieldDispatchJob.save

    def refuse_results(self, *args, **kwargs):
        if kwargs.get("update_fields") == ["results", "client_actions"]:
            raise DataError("unsupported Unicode escape sequence")
        return original_save(self, *args, **kwargs)

    with (
        mock_advocate_request({"ok": True}),
        patch.object(ButtonFieldDispatchJob, "save", refuse_results),
    ):
        with pytest.raises(DataError):
            _run(user, button_field, row)

    job = ButtonFieldDispatchJob.objects.get()
    assert job.state == JOB_FAILED
    assert job.results is None


def test_denied_message_reads_the_detail_of_an_api_error():
    class Quota(APIException):
        status_code = 403

    assert denied_message(Quota(detail="Quota exceeded.")) == "Quota exceeded."
    assert (
        denied_message(Quota(detail={"error": "ERROR_QUOTA", "detail": "Upgrade."}))
        == "Upgrade."
    )
    assert denied_message(PermissionException()) == (
        "You don't have the required permission to execute this operation."
    )


@pytest.mark.django_db
def test_a_click_cancelled_while_running_starts_no_further_action(
    data_fixture, dispatched_clicks
):
    """The owner can cancel a running job. The action running then finishes,
    but no later one starts."""

    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)
    _add_row_action(data_fixture, button_field, table, name_field, "later")

    with patch("baserow.core.jobs.handler.run_async_job"):
        job = JobHandler().create_and_start_job(
            user,
            ButtonFieldDispatchJobType.type,
            field=button_field,
            row_id=row.id,
            accepted_actions=_accepted_ids(button_field),
        )

    with mock_advocate_request({"ok": True}) as request:
        answer = request.side_effect

        def cancel_while_sending(*args, **kwargs):
            JobHandler.cancel_job(ButtonFieldDispatchJob.objects.get(id=job.id))
            return answer(*args, **kwargs)

        request.side_effect = cancel_while_sending
        run_async_job(job.id)

    job.refresh_from_db()
    assert request.called
    assert job.state == JOB_CANCELLED
    assert table.get_model().objects.exclude(id=row.id).count() == 0
    assert dispatched_clicks == []


@pytest.mark.django_db(transaction=True)
def test_a_button_retyped_while_its_click_runs_still_finishes_the_job(data_fixture):
    """A retype mid-run leaves the job's field alone, so the job that already
    passed its checks finishes."""

    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)

    with patch("baserow.core.jobs.handler.run_async_job"):
        job = JobHandler().create_and_start_job(
            user,
            ButtonFieldDispatchJobType.type,
            field=button_field,
            row_id=row.id,
            accepted_actions=_accepted_ids(button_field),
        )

    with mock_advocate_request({"ok": True}) as request:
        answer = request.side_effect

        def retype_while_sending(*args, **kwargs):
            FieldHandler().update_field(user, button_field, new_type_name="text")
            return answer(*args, **kwargs)

        request.side_effect = retype_while_sending
        run_async_job(job.id)

    job = ButtonFieldDispatchJob.objects.get(id=job.id)
    assert job.state == JOB_FINISHED
    assert job.field_id == button_field.id


@pytest.mark.django_db(transaction=True)
def test_a_button_deleted_while_its_click_runs_still_finishes_the_job(
    data_fixture,
):
    """Deleting the field empties the job's field in the database while the
    worker still holds the old id; saving the finished job must not write it
    back. The delete's set null is done directly: the delete itself cannot
    run inside the request the action sends."""

    user = data_fixture.create_user()
    table, name_field, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)

    with patch("baserow.core.jobs.handler.run_async_job"):
        job = JobHandler().create_and_start_job(
            user,
            ButtonFieldDispatchJobType.type,
            field=button_field,
            row_id=row.id,
            accepted_actions=_accepted_ids(button_field),
        )

    with mock_advocate_request({"ok": True}) as request:
        answer = request.side_effect

        def delete_while_sending(*args, **kwargs):
            ButtonFieldDispatchJob.objects.filter(id=job.id).update(field=None)
            return answer(*args, **kwargs)

        request.side_effect = delete_while_sending
        run_async_job(job.id)

    job = ButtonFieldDispatchJob.objects.get(id=job.id)
    assert job.state == JOB_FINISHED
    assert job.field_id is None


def test_a_click_that_ran_too_long_says_so_without_the_job_type():
    from celery.exceptions import SoftTimeLimitExceeded

    message = ButtonFieldDispatchJobType.job_exceptions_map[SoftTimeLimitExceeded]
    assert "button_field_dispatch" not in message
