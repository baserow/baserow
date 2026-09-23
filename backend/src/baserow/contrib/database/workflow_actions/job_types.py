from contextlib import nullcontext
from time import perf_counter
from typing import Any, Dict, List

from django.contrib.auth.models import AbstractUser

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from baserow.contrib.database.api.workflow_actions.serializers import (
    dispatch_result_payload,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionDispatchError,
    WorkflowActionDispatchInProgress,
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
from baserow.core.jobs.registries import JobType
from baserow.core.utils import Progress


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
        return {"field": values["field"], "row_id": values["row_id"]}

    def transaction_atomic_context(self, job: ButtonFieldDispatchJob):
        # Completed actions stay when a later one fails (ADR 006 section 3).
        return nullcontext()

    def run(self, job: ButtonFieldDispatchJob, progress: Progress) -> None:
        # Reading `job.user` restores the clicker's websocket id on it.
        user = job.user
        field = job.field
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

        try:
            row = RowHandler().get_row(user, field.table, job.row_id)
            workflow_actions = service.get_dispatch_snapshot(field)
            dispatch = service.dispatch_workflow_actions(
                user,
                field,
                row,
                workflow_actions=workflow_actions,
                on_action_failed=failed_positions.append,
            )
        except Exception as exc:
            outcome, failed_position = outcome_for(exc)
            send_dispatched(
                outcome, failed_position or next(iter(failed_positions), None)
            )
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

        payload = dispatch_result_payload(dispatch, user)
        job.results = payload["results"]
        job.client_actions = payload["client_actions"]
        job.save(update_fields=["results", "client_actions"])

        send_dispatched(DispatchOutcome.COMPLETED)
