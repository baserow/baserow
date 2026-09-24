import json
import math
from contextlib import nullcontext
from datetime import timedelta
from time import perf_counter
from typing import Any, Dict, List

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

from rest_framework import serializers
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.utils.encoders import JSONEncoder

from baserow.api.errors import ERROR_PERMISSION_DENIED
from baserow.contrib.database.api.workflow_actions.serializers import (
    dispatch_result_payload,
)
from baserow.contrib.database.fields.exceptions import FieldDoesNotExist
from baserow.contrib.database.rows.exceptions import RowDoesNotExist
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionClickExpired,
    WorkflowActionDispatchDenied,
    WorkflowActionDispatchError,
    WorkflowActionDispatchInProgress,
    WorkflowActionsChangedSinceClick,
    WorkflowActionTypeDeactivated,
)
from baserow.contrib.database.workflow_actions.models import (
    ButtonFieldDispatchJob,
    DatabaseWorkflowAction,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.contrib.database.workflow_actions.signals import button_field_dispatched
from baserow.contrib.database.workflow_actions.telemetry import (
    outcome_for,
    result_label,
)
from baserow.contrib.database.workflow_actions.types import DispatchOutcome
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.jobs.exceptions import JobCancelled
from baserow.core.jobs.registries import JobType
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import Progress


def denied_message(exc: Exception) -> str:
    """
    What the clicker reads when the click was refused while its job waited.
    A plugin's `APIException` carries a message meant for them, a SaaS quota
    for instance. A core permission refusal carries internal wording, or
    none, so it gets the one the refused request would have answered with.

    :param exc: What refused the click.
    :return: The message for the clicker.
    """

    if isinstance(exc, APIException):
        detail = exc.detail
        # Baserow's own API errors carry `{"error": ..., "detail": ...}`.
        if isinstance(detail, dict):
            detail = detail.get("detail")
        if isinstance(detail, str) and detail:
            return str(detail)
    return ERROR_PERMISSION_DENIED[2]


def jsonb_safe(value: Any) -> Any:
    """
    The click's payload as Postgres can store it. The inline response was
    rendered by DRF, which accepts what a jsonb column refuses: a NUL
    character in an endpoint's answer, a float that is not a number, a date.

    :param value: The payload.
    :return: The same payload with those replaced.
    """

    def clean(item):
        if isinstance(item, str):
            return item.replace("\x00", "")
        if isinstance(item, float) and not math.isfinite(item):
            return None
        if isinstance(item, dict):
            return {clean(key): clean(val) for key, val in item.items()}
        if isinstance(item, (list, tuple)):
            return [clean(val) for val in item]
        return item

    return clean(json.loads(json.dumps(clean(value), cls=JSONEncoder)))


def _own_message(exc: Exception) -> str:
    # The framework formats the mapped message with `.format(e=e)`, so a brace
    # in an endpoint's answer would break it.
    return str(exc).replace("{", "{{").replace("}", "}}")


class ButtonFieldDispatchJobType(JobType):
    """
    Runs a button click whose actions reach outside Baserow, so the request
    that received the click returns at once and no WSGI worker waits on the
    other side. Started by the dispatch view only.
    """

    type = "button_field_dispatch"
    model_class = ButtonFieldDispatchJob
    max_count = 5
    queue = "button_dispatch"

    job_exceptions_map = {
        WorkflowActionDispatchError: _own_message,
        WorkflowActionDispatchInProgress: "Another click on this row is still running.",
        # A race between enqueue and run: the field, the row, the workspace
        # membership or the type's activation can change while the job is
        # queued. Mapped so the job fails with a message instead of raising
        # out of the task.
        FieldDoesNotExist: "The button no longer exists.",
        RowDoesNotExist: "The clicked row no longer exists.",
        UserNotInWorkspace: "The clicker is no longer a member of the workspace.",
        WorkflowActionTypeDeactivated: _own_message,
        WorkflowActionClickExpired: (
            "The click waited too long to run and was dropped. Click again."
        ),
        WorkflowActionsChangedSinceClick: (
            "The button's actions changed while the click was waiting. "
            "Click again to run the new ones."
        ),
        # A plugin refusing the click (a SaaS quota, for instance) gets its
        # own message too, and does not raise out of the task: the refusal is
        # not a bug to alert on.
        WorkflowActionDispatchDenied: _own_message,
    }

    request_serializer_field_names = []
    serializer_field_names = ["results", "client_actions"]
    serializer_field_overrides = {
        "results": serializers.JSONField(read_only=True, allow_null=True),
        "client_actions": serializers.JSONField(read_only=True, allow_null=True),
    }

    def prepare_values(
        self, values: Dict[str, Any], user: AbstractUser
    ) -> Dict[str, Any]:
        # The generic jobs endpoint cannot name a field, so it cannot start one
        # of these; only the dispatch view can, after its own checks.
        if "field" not in values or "row_id" not in values:
            raise ValidationError("A button click job is started by clicking a button.")
        return {
            "field": values["field"],
            "row_id": values["row_id"],
            "accepted_actions": values.get("accepted_actions", []),
        }

    def transaction_atomic_context(self, job: ButtonFieldDispatchJob):
        # Completed actions stay when a later one fails (ADR 006 section 3).
        return nullcontext()

    def run(self, job: ButtonFieldDispatchJob, progress: Progress) -> None:
        # Reading `job.user` restores the clicker's websocket id on it.
        user = job.user
        # The cleanup fails a job this old and frees its cell, so another click
        # may already be running the same actions.
        if job.created_on < timezone.now() - timedelta(
            seconds=settings.BASEROW_JOB_SOFT_TIME_LIMIT
        ):
            raise WorkflowActionClickExpired()
        field = job.field
        # Retyped or trashed while the job waited on the queue, the field or
        # anything above it. Refused before the click event, as the view
        # refuses a missing field before it sends one.
        if field is None or TrashHandler.item_has_a_trashed_parent(
            field, check_item_also=True
        ):
            raise FieldDoesNotExist()
        service = DatabaseWorkflowActionService()

        started = perf_counter()
        workflow_actions: List[DatabaseWorkflowAction] = []
        failed_positions: List[int] = []
        error_status_count = 0

        def send_dispatched(outcome, failed_position=None):
            button_field_dispatched.send_robust(
                self.__class__,
                user=user,
                field=field,
                row_id=job.row_id,
                workflow_actions=workflow_actions,
                outcome=outcome,
                failed_position=failed_position,
                error_status_count=error_status_count,
                duration_ms=(perf_counter() - started) * 1000,
            )

        def stop_if_cancelled():
            # The owner can cancel a running job. Checked between actions, so
            # none starts after that, while the ones that ran stay.
            if job.cancelled:
                raise JobCancelled()

        try:
            row = RowHandler().get_row(user, field.table, job.row_id)
            workflow_actions = service.get_dispatch_snapshot(field)
            # The request checked and charged the list it accepted. An action
            # added, removed or reordered while the job waited would run
            # unchecked, and an added external one without a slot reserved.
            if service.accepted_actions(workflow_actions) != job.accepted_actions:
                raise WorkflowActionsChangedSinceClick()
            dispatch = service.dispatch_workflow_actions(
                user,
                field,
                row,
                workflow_actions=workflow_actions,
                on_action_failed=failed_positions.append,
                before_action=stop_if_cancelled,
            )
        except Exception as exc:
            # Anyone could send a click that fails this way, so it must not
            # tag another workspace's ids in the event (mirrors the inline
            # dispatch view).
            # A cancelled click is the clicker's choice, not an outcome.
            if not isinstance(exc, (UserNotInWorkspace, JobCancelled)):
                outcome, failed_position = outcome_for(exc)
                send_dispatched(
                    outcome, failed_position or next(iter(failed_positions), None)
                )
                if outcome == DispatchOutcome.DENIED:
                    # A refusal can be any exception type: a
                    # `PermissionException`, Django's `PermissionDenied`, or
                    # any `APIException` with a 403 status. None of those is
                    # one `job_exceptions_map` can list by class alone, so it
                    # is re-raised as one that is.
                    raise WorkflowActionDispatchDenied(denied_message(exc)) from exc
            raise
        except BaseException:
            send_dispatched(DispatchOutcome.ERROR, next(iter(failed_positions), None))
            raise

        # An endpoint that answered with an error status is a completed
        # action; counted so the click's event says so.
        error_status_count = sum(
            1
            for dispatched in dispatch.dispatched
            if dispatched.result is not None
            and result_label(True, dispatched.result) == "error_status"
        )

        payload = jsonb_safe(dispatch_result_payload(dispatch, user))
        job.results = payload["results"]
        job.client_actions = payload["client_actions"]
        job.save(update_fields=["results", "client_actions"])

        send_dispatched(DispatchOutcome.COMPLETED)
