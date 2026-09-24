import json
from contextlib import contextmanager, nullcontext
from dataclasses import fields as dataclass_fields
from datetime import timedelta
from time import perf_counter
from typing import Any, Callable, Dict, List, Optional

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.db import DEFAULT_DB_ALIAS, transaction
from django.db.models import Q
from django.utils import timezone

from loguru import logger
from opentelemetry import trace
from opentelemetry.instrumentation.utils import suppress_http_instrumentation
from redis.exceptions import LockNotOwnedError

from baserow.contrib.database.fields.models import ButtonField
from baserow.contrib.database.fields.operations import (
    ReadFieldOperationType,
    UpdateFieldOperationType,
)
from baserow.contrib.database.workflow_actions.dispatch_context import (
    DatabaseDispatchContext,
)
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionDispatchError,
    WorkflowActionDispatchInProgress,
)
from baserow.contrib.database.workflow_actions.handler import (
    DatabaseWorkflowActionHandler,
)
from baserow.contrib.database.workflow_actions.models import (
    ButtonFieldDispatchJob,
    DatabaseWorkflowAction,
)
from baserow.contrib.database.workflow_actions.operations import (
    DispatchDatabaseWorkflowActionOperationType,
)
from baserow.contrib.database.workflow_actions.reconfiguration import (
    annotate_actions_requiring_reconfiguration,
)
from baserow.contrib.database.workflow_actions.registries import (
    DatabaseWorkflowActionType,
    database_workflow_action_type_registry,
)
from baserow.contrib.database.workflow_actions.signals import (
    workflow_action_created,
    workflow_action_dispatched,
    workflow_action_updated,
    workflow_actions_before_dispatch,
    workflow_actions_reordered,
)
from baserow.contrib.database.workflow_actions.types import (
    DispatchedWorkflowAction,
    UpdatedDatabaseWorkflowAction,
    WorkflowActionsDispatchResult,
)
from baserow.core.action.context import without_undo_redo_registration
from baserow.core.action.registries import action_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.jobs.constants import JOB_PENDING, JOB_STARTED
from baserow.core.services.exceptions import (
    DoesNotExist,
    InvalidContextContentDispatchException,
    InvalidContextDispatchException,
    PermissionDeniedDispatchException,
    ServiceImproperlyConfiguredDispatchException,
    TriggerServiceNotDispatchable,
    UnexpectedDispatchException,
    UnreachableAddressDispatchException,
)
from baserow.core.services.models import Service
from baserow.core.services.types import DispatchResult
from baserow.core.telemetry.utils import (
    add_baserow_trace_attrs,
    baserow_trace_phase,
)
from baserow.core.trash.handler import TrashHandler

# What a failed external action tells the clicker. The service's own message
# names the URL it could not reach, which is where an API key would be.
EXTERNAL_DISPATCH_FAILED_MESSAGE = "the request could not be completed"

# Failures whose message can name where the request was going: the URL with its
# query string, or the instance's own mail host. An external action never
# repeats these to the clicker. Listed rather than excluded, so a new failure
# stays readable until it is known to name an address.
ADDRESS_BEARING_DISPATCH_EXCEPTIONS = (
    UnexpectedDispatchException,
    UnreachableAddressDispatchException,
)

tracer = trace.get_tracer(__name__)


USER_FACING_DISPATCH_EXCEPTIONS = (
    ServiceImproperlyConfiguredDispatchException,
    InvalidContextDispatchException,
    InvalidContextContentDispatchException,
    PermissionDeniedDispatchException,
    TriggerServiceNotDispatchable,
    DoesNotExist,
)


def _shape_of(value: Any) -> Any:
    """
    What an answer looks like with its values taken out, so two answers that
    differ only in what they contain compare equal.

    :param value: Any part of a remembered answer.
    :return: The same structure with every leaf replaced by its type name.
    """

    if isinstance(value, dict):
        return {key: _shape_of(each) for key, each in sorted(value.items())}
    if isinstance(value, list):
        return [_shape_of(each) for each in value]
    return type(value).__name__


def _describes_the_same_shape(stored: Any, fresh: Any) -> bool:
    """
    :param stored: What the service remembers, as it comes out of the column.
    :param fresh: What this click would remember.
    :return: True when the editor would build the same schema from either.
    """

    if not stored or "_error" in stored:
        return False

    return _shape_of(stored) == _shape_of(json.loads(json.dumps(fresh, default=str)))


class DatabaseWorkflowActionService:
    """
    Permission-checking layer over `DatabaseWorkflowActionHandler`.

    Configuring a button field's actions is configuring the field, so every
    check runs against the parent field rather than against action-specific
    operations (ADR 006 section 5).
    """

    def __init__(self):
        self.handler = DatabaseWorkflowActionHandler()

    def get_workflow_actions(
        self, user: AbstractUser, field: ButtonField
    ) -> List[DatabaseWorkflowAction]:
        # An action carries the schema of the table it writes to, which the
        # reader may have no access to.
        CoreHandler().check_permissions(
            user,
            UpdateFieldOperationType.type,
            workspace=field.table.database.workspace,
            context=field,
        )

        return list(
            self.handler.get_workflow_actions(
                field,
                base_queryset=annotate_actions_requiring_reconfiguration(
                    DatabaseWorkflowAction.objects.all()
                ),
            )
        )

    def create_workflow_action(
        self,
        user: AbstractUser,
        workflow_action_type: DatabaseWorkflowActionType,
        field: ButtonField,
        **kwargs,
    ) -> DatabaseWorkflowAction:
        CoreHandler().check_permissions(
            user,
            UpdateFieldOperationType.type,
            workspace=field.table.database.workspace,
            context=field,
        )

        workflow_action_type.raise_if_deactivated(field.table.database.workspace)

        # The type reads the field to know which database an integration
        # may come from.
        prepared_values = workflow_action_type.prepare_values(
            {**kwargs, "field": field}, user
        )
        workflow_action = self.handler.create_workflow_action(
            workflow_action_type, field=field, **prepared_values
        )

        workflow_action_created.send(self, workflow_action=workflow_action, user=user)

        return workflow_action

    def update_workflow_action(
        self,
        user: AbstractUser,
        workflow_action: DatabaseWorkflowAction,
        keep_replaced_service: bool = False,
        **kwargs,
    ) -> UpdatedDatabaseWorkflowAction:
        """
        Updates an action, swapping its type in place when `type` changes.

        :param user: Who is updating the action.
        :param workflow_action: The action to update.
        :param keep_replaced_service: Whether a type change leaves the service
            it replaces in place, for an undo to attach again, rather than
            deleting it.
        :return: The updated action with its values before and after.
        """

        field = workflow_action.field
        CoreHandler().check_permissions(
            user,
            UpdateFieldOperationType.type,
            workspace=field.table.database.workspace,
            context=field,
        )

        # Read before `prepare_values` writes to the service.
        original_values = workflow_action.get_type().export_prepared_values(
            workflow_action
        )

        has_type_changed = (
            "type" in kwargs and kwargs["type"] != workflow_action.get_type().type
        )

        if has_type_changed:
            # Swapped in place rather than recreated, so an update answers with
            # the action it was given rather than a different one.
            workflow_action_type = database_workflow_action_type_registry.get(
                kwargs["type"]
            )
            workflow_action_type.raise_if_deactivated(field.table.database.workspace)
            prepared_values = workflow_action_type.prepare_values(
                {**kwargs, "field": field}, user
            )
            workflow_action = self.handler.change_workflow_action_type(
                workflow_action,
                workflow_action_type,
                keep_old_service=keep_replaced_service,
                **prepared_values,
            )
        else:
            workflow_action_type = workflow_action.get_type()
            prepared_values = workflow_action_type.prepare_values(
                kwargs, user, workflow_action
            )
            workflow_action = self.handler.update_workflow_action(
                workflow_action, **prepared_values
            )

        workflow_action_updated.send(self, workflow_action=workflow_action, user=user)

        return UpdatedDatabaseWorkflowAction(
            workflow_action,
            original_values,
            workflow_action.get_type().export_prepared_values(workflow_action),
        )

    def restore_workflow_action_type(
        self,
        user: AbstractUser,
        workflow_action: DatabaseWorkflowAction,
        values: Dict[str, Any],
        service: Optional[Service],
    ) -> DatabaseWorkflowAction:
        """
        Swaps an action back to a type it had, for an undo or a redo, with the
        service it had then. The logged values leave out whatever the service
        calls sensitive, so building a new service from them would blank those
        fields. The service the action has now is kept for the opposite step.

        :param user: Who is undoing or redoing.
        :param workflow_action: The action to swap.
        :param values: The action's logged values, `type` among them. The
            service's own values are ignored in favour of `service`.
        :param service: The service to attach, or None for a type without one.
        :return: The action, now an instance of the restored type's model.
        """

        field = workflow_action.field
        CoreHandler().check_permissions(
            user,
            UpdateFieldOperationType.type,
            workspace=field.table.database.workspace,
            context=field,
        )

        workflow_action_type = database_workflow_action_type_registry.get(
            values["type"]
        )
        workflow_action_type.raise_if_deactivated(field.table.database.workspace)
        config = {
            key: value
            for key, value in values.items()
            if key not in ("type", "service")
        }
        if service is not None:
            workflow_action_type.check_kept_service(service, user, field)
            config["service"] = service

        workflow_action = self.handler.change_workflow_action_type(
            workflow_action, workflow_action_type, keep_old_service=True, **config
        )

        workflow_action_updated.send(self, workflow_action=workflow_action, user=user)

        return workflow_action

    def delete_workflow_action(
        self, user: AbstractUser, workflow_action: DatabaseWorkflowAction
    ) -> None:
        field = workflow_action.field
        CoreHandler().check_permissions(
            user,
            UpdateFieldOperationType.type,
            workspace=field.table.database.workspace,
            context=field,
        )

        # Trashed rather than deleted, so an undo can bring it back with its
        # service. The trash type sends `workflow_action_deleted`.
        database = field.table.database
        TrashHandler.trash(user, database.workspace, database, workflow_action)

    def order_workflow_actions(
        self, user: AbstractUser, field: ButtonField, order: List[int]
    ) -> List[int]:
        CoreHandler().check_permissions(
            user,
            UpdateFieldOperationType.type,
            workspace=field.table.database.workspace,
            context=field,
        )

        full_order = self.handler.order_workflow_actions(field, order)

        workflow_actions_reordered.send(self, field=field, order=full_order, user=user)

        return full_order

    def _resolve_integrations(self, services: List[Service]) -> None:
        """
        Puts the specific integration on each service that carries one, in one
        query for the whole click.

        A service's `enhance_queryset` fetches the base row, but the credential
        lives on the subtype, and resolving that row by row costs a query per
        action. Three actions sharing one bot read it three times, inside the
        lock that guards the row.

        `get_specific` returns the instance unchanged when it already is the
        subtype, so assigning these here means nothing queries again later.

        :param services: The specific services this click will dispatch.
        :return: Nothing. The services are updated in place.
        """

        carrying = [service for service in services if service.integration_id]
        if not carrying:
            return

        # Through the handler rather than `specific_iterator` directly, so an
        # integration type's own `enhance_queryset` still runs and this does
        # not trade one query per action for one per related row.
        by_id = {
            integration.id: integration
            for integration in IntegrationHandler().get_integrations(
                base_queryset=Integration.objects.filter(
                    id__in={service.integration_id for service in carrying}
                )
            )
        }
        for service in carrying:
            integration = by_id.get(service.integration_id)
            if integration is not None:
                service.integration = integration

    def _lock_ttl_for(
        self, server_actions: List[DatabaseWorkflowAction], services: List[Service]
    ) -> int:
        """
        How long the lock outlives the click that took it. The setting is a
        floor rather than the answer: it covers a sequence of ordinary actions,
        but a button may chain several requests that are each allowed to run
        for as long as the whole default. A lock that expires mid sequence
        stops protecting the row, which is what it is there for.

        :param server_actions: The actions this click will run, in order.
        :param services: Their specific services, in the same order.
        :return: The TTL in seconds.
        """

        # The service type owns the number: an email waits on its server
        # without carrying a timeout field of its own.
        waiting_on = sum(
            service.get_type().max_dispatch_seconds(service)
            for workflow_action, service in zip(server_actions, services)
            if workflow_action.get_type().is_external
        )
        return max(settings.DATABASE_BUTTON_DISPATCH_LOCK_TTL_SECONDS, waiting_on * 2)

    def _remember_result_shape(
        self, workflow_action: DatabaseWorkflowAction, result: DispatchResult
    ) -> None:
        """
        Keeps what an external action returned, so the editor can describe it
        to the actions after it. An endpoint's answer has no schema until it
        has answered once, and a button has no preview to ask with.

        Only types that ask for it: keeping a row action's result would write a
        real row's values into the field's configuration.

        :param workflow_action: The action that just ran.
        :param result: What it returned.
        """

        workflow_action_type = workflow_action.get_type()

        if not workflow_action_type.captures_sample_data:
            return

        # The type decides: a 404 error page is still a successful dispatch
        # and describes nothing, and a type with no status code answers this
        # differently. Keeping it would drop the shape an earlier click learned.
        unusable = workflow_action_type.unusable_result_reason(result)
        if unusable:
            self._remember_nothing_was_captured(workflow_action, unusable)
            return

        sample_data = {
            f.name: getattr(result, f.name) for f in dataclass_fields(result)
        }

        try:
            # `ensure_ascii=False`, or the cap measures escape sequences
            # rather than what the column holds: a Japanese answer inflates
            # about twofold and a Cyrillic or emoji one threefold, so an
            # answer well under the limit would be refused for its alphabet.
            encoded = json.dumps(sample_data, ensure_ascii=False)

            max_bytes = settings.DATABASE_BUTTON_SAMPLE_DATA_MAX_BYTES
            if len(encoded.encode("utf-8")) > max_bytes:
                # A big response still reached the clicker; it is only its
                # shape that the editor goes without.
                self._remember_nothing_was_captured(
                    workflow_action,
                    f"The last click was answered with more than the "
                    f"{max_bytes} bytes this installation keeps.",
                )
                return

            service = workflow_action.service
            # Compared on shape rather than on values. The answer carries every
            # response header, and `Date` alone changes every second, so a
            # comparison of the whole thing would almost never match and every
            # click would rewrite a TOASTed blob for nothing. The editor reads
            # this only to build a schema, so a differently shaped answer is
            # the only one worth the write.
            if _describes_the_same_shape(service.sample_data, sample_data):
                return

            service.sample_data = sample_data
            # Its own savepoint: a value the column refuses would otherwise
            # leave an enclosing transaction unusable for the actions after
            # this one.
            with transaction.atomic():
                service.save(update_fields=["sample_data"])
        except Exception as exc:
            # Never fail a click that already succeeded. What an endpoint can
            # answer with is not ours to predict: a NaN or a NUL byte encodes
            # here and is then refused by the column it is written to, and by
            # this point the request has left and earlier actions have already
            # written their rows.
            # Not the exception itself: loguru prints the frame locals beside
            # the traceback, and this frame holds the answer, response headers
            # included. Only the class of the failure is logged.
            logger.warning(
                "Could not remember the result of workflow action "
                "{action_id}: {exception}. The failure itself is not logged: "
                "the frame holds what the endpoint answered with.",
                action_id=workflow_action.id,
                exception=type(exc).__name__,
            )

    def _send_workflow_action_dispatched(
        self,
        workflow_action: DatabaseWorkflowAction,
        dispatch_context: DatabaseDispatchContext,
        position: int,
        result: Optional[DispatchResult],
        duration_ms: float,
    ) -> None:
        """
        Tells receivers what one action did. The action already ran, so a
        receiver that fails must not fail the click. Called outside the
        dispatch's `except`, or a receiver's failure would chain the dispatch
        failure, whose text can name the address, into the log of it.

        The signal sends robustly and logs a failing receiver by its class,
        except that its log reads `receiver.__qualname__`, which a callable
        object has not, so the send is wrapped too. Only the failure's class
        is logged: the frames hold the result and the address it went to.

        :param workflow_action: The action that was dispatched.
        :param dispatch_context: The click's dispatch context.
        :param position: The action's position in the button's actions.
        :param result: What the action returned, or None when it failed.
        :param duration_ms: How long the dispatch ran.
        """

        try:
            responses = workflow_action_dispatched.send_robust(
                self,
                workflow_action=workflow_action,
                dispatch_context=dispatch_context,
                field=dispatch_context.field,
                position=position,
                succeeded=result is not None,
                result=result,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            logger.error(
                "A workflow_action_dispatched receiver failed for workflow action "
                "{action_id} of button field {field_id} with {exception}, and the "
                "receivers behind it did not run.",
                action_id=workflow_action.id,
                field_id=dispatch_context.field.id,
                exception=type(exc).__name__,
            )
            return

        # Django's own log of these names neither the action nor the field.
        for _, response in responses:
            if isinstance(response, Exception):
                logger.error(
                    "A workflow_action_dispatched receiver failed for workflow "
                    "action {action_id} of button field {field_id} with "
                    "{exception}.",
                    action_id=workflow_action.id,
                    field_id=dispatch_context.field.id,
                    exception=type(response).__name__,
                )

    def get_dispatch_snapshot(self, field: ButtonField) -> List[DatabaseWorkflowAction]:
        """
        The actions a click is about to run, read once so what it is charged
        for and what it runs are the same list. Reading it twice lets a
        configuration change land in between.

        No permission check: `dispatch_workflow_actions` makes them all.

        :param field: The clicked button field.
        :return: Its actions, in the order they run.
        """

        return list(self.handler.get_workflow_actions(field))

    def accepted_actions(
        self, workflow_actions: List[DatabaseWorkflowAction]
    ) -> List[List]:
        """
        What a click was accepted with, to tell later whether it still runs
        the same actions. The type is part of it: a retype keeps the id, and
        can turn an action the click was not charged for into an external one.

        :param workflow_actions: The actions of the click, in order.
        :return: One [id, type] pair per action.
        """

        return [[wa.id, wa.get_type().type] for wa in workflow_actions]

    @contextmanager
    def cell_lock(self, prefix: str, field: ButtonField, row_id: int, timeout: int):
        """
        Holds a lock on one cell of the button for the length of the block.
        Never waits: a second click is refused rather than queued behind one
        that still holds it. Released by a script that checks ownership first,
        so a click whose TTL ran out cannot drop a later click's lock. Keyed on
        field and row together, so two buttons on one row do not block each
        other.

        :param prefix: What the lock guards, so two locks on a cell can coexist.
        :param field: The clicked button field.
        :param row_id: The clicked row.
        :param timeout: Seconds after which the lock frees itself.
        :raises WorkflowActionDispatchInProgress: When the cell is already held.
        """

        lock = cache.lock(f"{prefix}_{field.id}_{row_id}", timeout=timeout)
        if not lock.acquire(blocking=False):
            raise WorkflowActionDispatchInProgress()
        try:
            yield
        finally:
            try:
                lock.release()
            except LockNotOwnedError:
                # The TTL ran out inside the block, so the key is a later
                # click's to release.
                pass

    def has_click_in_flight(
        self,
        field: ButtonField,
        row_id: int,
        workflow_actions: List[DatabaseWorkflowAction],
    ) -> bool:
        """
        Whether a click on this cell is still waiting for, or running in, a
        job. A second click is refused while one is.

        A job whose worker died never leaves its state, so each state counts
        only for as long as it can legitimately last: a started click for the
        TTL its row lock would have, a pending one until the job cleanup fails
        it. Past that the cell is free again, as it was when the row lock
        alone guarded it.

        :param field: The clicked button field.
        :param row_id: The clicked row.
        :param workflow_actions: The actions of the new click, which bound how
            long a started click on the cell can be running.
        :return: True when a live pending or started job exists for the cell.
        """

        server_actions = [
            wa for wa in workflow_actions if not wa.get_type().is_frontend_only
        ]
        services = [wa.service.specific for wa in server_actions]
        now = timezone.now()
        started_since = now - timedelta(
            seconds=self._lock_ttl_for(server_actions, services)
        )
        pending_since = now - timedelta(seconds=settings.BASEROW_JOB_SOFT_TIME_LIMIT)
        # On the primary: a replica a moment behind would miss the job a click
        # just created, and let a second one through.
        return (
            ButtonFieldDispatchJob.objects.using(DEFAULT_DB_ALIAS)
            .filter(field=field, row_id=row_id)
            .filter(
                Q(state=JOB_STARTED, updated_on__gte=started_since)
                | Q(state=JOB_PENDING, updated_on__gte=pending_since)
            )
            .exists()
        )

    def _remember_nothing_was_captured(
        self, workflow_action: DatabaseWorkflowAction, reason: str
    ) -> None:
        """
        Leaves the editor a note saying why the last click described nothing,
        rather than letting it keep asking for a click that has already
        happened.

        Only written when there is no shape to lose. A shape an earlier click
        learned is worth more than an explanation of the latest one, and every
        action pointing at that shape would break with it. An earlier
        explanation is replaced, though: a 404 followed by a timeout has to
        stop describing the 404 as the last click.

        :param workflow_action: The action that just ran.
        :param reason: What to tell whoever opens the editor. Says nothing
            about the address the action was pointed at.
        """

        service = workflow_action.service
        stored = service.sample_data
        note = {"_error": reason}

        if stored and not (isinstance(stored, dict) and "_error" in stored):
            return

        if stored == note:
            # The same click again. Nothing to rewrite.
            return

        try:
            service.sample_data = note
            # Its own savepoint, for the same reason the capture below has one.
            with transaction.atomic():
                service.save(update_fields=["sample_data"])
        except Exception:
            logger.opt(exception=True).warning(
                "Could not record why workflow action {action_id} captured nothing.",
                action_id=workflow_action.id,
            )

    def dispatch_positions(
        self, workflow_actions: List[DatabaseWorkflowAction]
    ) -> Dict[int, int]:
        """
        Where each action sits in the sequence, by id, counting from one over
        the whole list, frontend-only actions included, so it matches what the
        clicker counts in the editor. Taken from the execution order rather
        than from `order`, which two actions can share.

        :param workflow_actions: The snapshot the click runs.
        :return: Action id to position.
        """

        return {
            workflow_action.id: index
            for index, workflow_action in enumerate(workflow_actions, start=1)
        }

    def check_dispatch_allowed(
        self,
        user: AbstractUser,
        field: ButtonField,
        workflow_actions: List[DatabaseWorkflowAction],
    ) -> None:
        """
        Refuses a click that cannot run as a whole, before anything is locked,
        reserved or enqueued. In order: the dispatch permission, a deactivated
        type, a misconfigured action.

        :param user: The user who clicked.
        :param field: The clicked button field.
        :param workflow_actions: The snapshot the click would run.
        :raises PermissionException: When the user may not click this button.
        :raises WorkflowActionTypeDeactivated: When a type cannot run here.
        :raises WorkflowActionDispatchError: When an action's saved
            configuration cannot run, named by its position.
        """

        # Asked of the field, so it covers every action, frontend-only
        # included, and a click is refused as a whole (ADR 006 section 7).
        CoreHandler().check_permissions(
            user,
            DispatchDatabaseWorkflowActionOperationType.type,
            workspace=field.table.database.workspace,
            context=field,
        )

        # After the permission check, since the reason describes how this
        # installation is configured and only a dispatcher may see it. Once
        # per type, in the order the actions run.
        checked_types = {}
        for workflow_action in workflow_actions:
            workflow_action_type = workflow_action.get_type()
            checked_types.setdefault(workflow_action_type.type, workflow_action_type)
        for workflow_action_type in checked_types.values():
            workflow_action_type.raise_if_deactivated(field.table.database.workspace)

        # An action whose saved configuration cannot run is known before the
        # click starts, and the actions ahead of it would not be rolled back.
        positions = self.dispatch_positions(workflow_actions)
        for workflow_action in workflow_actions:
            if workflow_action.get_type().is_frontend_only:
                continue
            try:
                workflow_action.get_type().raise_if_misconfigured(workflow_action)
            except ServiceImproperlyConfiguredDispatchException as exc:
                raise WorkflowActionDispatchError(
                    workflow_action.id, str(exc), positions[workflow_action.id]
                ) from exc

    def dispatch_workflow_actions(
        self,
        user: AbstractUser,
        field: ButtonField,
        row: Any,
        workflow_actions: Optional[List[DatabaseWorkflowAction]] = None,
        on_action_failed: Optional[Callable[[int], None]] = None,
        before_action: Optional[Callable[[], None]] = None,
    ) -> WorkflowActionsDispatchResult:
        """
        Runs the server-side actions in order as the given user, and hands the
        frontend-only ones back for the caller to run.

        Not wrapped in a transaction: completed actions must stay when a later
        one fails, since a sequence can have irreversible effects that no
        rollback undoes (ADR 006 section 3).

        :param user: The user who clicked.
        :param field: The clicked button field.
        :param row: The clicked row.
        :param workflow_actions: The actions to run, from
            `get_dispatch_snapshot`. Read here when the caller has none.
        :param on_action_failed: Called with the position of the action that
            failed, whatever it raised.
        :param before_action: Called before each server action. It may raise to
            stop the click there, keeping what already ran.
        :raises WorkflowActionDispatchInProgress: When a click is already running
            for this field and row.
        :raises WorkflowActionDispatchError: When an action fails with a message
            meant for the clicker. Any other failure is re-raised as it is, so
            its message stays server side. Either way the actions before it have
            already run and are not rolled back.
        :return: What the server-side actions returned, and the frontend-only
            actions for the caller to run itself, both in order.
        """

        # Imported here: the action module reads this service.
        from baserow.contrib.database.workflow_actions.actions import (
            DispatchButtonFieldActionType,
        )

        # Field scoped, so it also covers a button with no actions: without it
        # an outsider would get an empty result rather than a refusal.
        CoreHandler().check_permissions(
            user,
            ReadFieldOperationType.type,
            workspace=field.table.database.workspace,
            context=field,
        )

        if workflow_actions is None:
            workflow_actions = self.get_dispatch_snapshot(field)

        # On the request's span: one of its own would be marked failed by every
        # refused click, a double click included.
        add_baserow_trace_attrs(
            field_id=field.id,
            workspace_id=field.table.database.workspace_id,
            action_count=len(workflow_actions),
        )

        if not workflow_actions:
            return WorkflowActionsDispatchResult()

        # Before the lock is taken, so a refused user never holds it.
        self.check_dispatch_allowed(user, field, workflow_actions)

        # Frontend-only actions can't be dispatched here; the caller runs them
        # in the browser.
        client_actions = [
            wa for wa in workflow_actions if wa.get_type().is_frontend_only
        ]
        server_actions = [
            wa for wa in workflow_actions if not wa.get_type().is_frontend_only
        ]
        positions = self.dispatch_positions(workflow_actions)

        # Nothing server side means no state to protect, so no lock: a button
        # that only opens a URL must not reject a second click.
        if not server_actions:
            action_type_registry.get(DispatchButtonFieldActionType.type).do(
                user, field, row, len(workflow_actions)
            )
            return WorkflowActionsDispatchResult(
                client_actions=client_actions, positions=positions
            )

        # Resolved once for both: `specific` caches on the instance, but only
        # while these are the objects the dispatch goes on to use.
        services = [
            workflow_action.service.specific for workflow_action in server_actions
        ]
        # Before the lock: it holds nothing the lock protects.
        self._resolve_integrations(services)

        # So a double click cannot run the sequence twice.
        with self.cell_lock(
            "button_dispatch",
            field,
            row.id,
            self._lock_ttl_for(server_actions, services),
        ):
            # With the lock held, so a receiver only sees a click that goes on
            # to run, and before the audit entry, so a receiver that refuses
            # the click (SaaS quota) leaves nothing behind. A copy: a receiver
            # that filtered the list in place would change what the click
            # then runs.
            workflow_actions_before_dispatch.send(
                self, user=user, field=field, workflow_actions=tuple(server_actions)
            )

            # Inside the lock, so a click refused as already running leaves no entry.
            action_type_registry.get(DispatchButtonFieldActionType.type).do(
                user, field, row, len(workflow_actions)
            )

            # Remembering a result edits the button's configuration, so it
            # follows the field's update permission rather than the lower bar
            # for clicking (ADR 006 section 7). Only asked when an action of
            # this button can remember anything, so an ordinary click does not
            # pay for a check nothing reads. Inside the lock's `try`, or a
            # check that raises would leave the lock held until its TTL runs
            # out and refuse every click on this row until then.
            may_configure = any(
                wa.get_type().captures_sample_data for wa in server_actions
            ) and CoreHandler().check_permissions(
                user,
                UpdateFieldOperationType.type,
                workspace=field.table.database.workspace,
                context=field,
                raise_permission_exceptions=False,
            )

            dispatch_context = DatabaseDispatchContext(user, field, row)
            dispatched = []

            # The clicker's own actions must not land in their undo stack
            # (ADR 006 section 8), while still firing `action_done`.
            with without_undo_redo_registration(user):
                for workflow_action in server_actions:
                    if before_action:
                        before_action()
                    # Each action reads the clicked row itself, so it sees what
                    # the actions before it did to it (ADR 006 section 4).
                    dispatch_context.start_action()
                    is_external = workflow_action.get_type().is_external
                    started = perf_counter()
                    exc = result = None
                    try:
                        # A span per action, so the type and position of one
                        # do not overwrite the last one's on the click's span.
                        # `record_exception=False`: the action's own failure
                        # can name the address it reached.
                        with baserow_trace_phase(
                            tracer,
                            "DatabaseWorkflowActionService.dispatch_workflow_action",
                            record_exception=False,
                        ):
                            add_baserow_trace_attrs(
                                workflow_action_type=workflow_action.get_type().type,
                                position=positions[workflow_action.id],
                            )
                            # The requests instrumentation's client span names
                            # the whole address, query string included, and
                            # would send the trace id to it.
                            with (
                                suppress_http_instrumentation()
                                if is_external
                                else nullcontext()
                            ):
                                result = self.handler.dispatch_workflow_action(
                                    workflow_action, dispatch_context
                                )
                    except BaseException as dispatch_exc:
                        # A worker timeout too, so the failed action is still
                        # counted before it propagates unchanged.
                        exc = dispatch_exc
                    self._send_workflow_action_dispatched(
                        workflow_action=workflow_action,
                        dispatch_context=dispatch_context,
                        position=positions[workflow_action.id],
                        result=result,
                        duration_ms=(perf_counter() - started) * 1000,
                    )
                    if exc is not None:
                        if on_action_failed:
                            on_action_failed(positions[workflow_action.id])
                        names_an_address = is_external and isinstance(
                            exc, ADDRESS_BEARING_DISPATCH_EXCEPTIONS
                        )
                        if is_external:
                            # Decided by where the action reaches rather than
                            # by which failure it is. Loguru prints the frame
                            # locals beside the traceback, and the frame that
                            # resolved the formulas holds the URL and every
                            # resolved header value whatever went wrong after
                            # it. So an external action never logs its own
                            # exception, only the ids and the class.
                            logger.error(
                                "Workflow action {action_id} of button field "
                                "{field_id} failed while reaching outside "
                                "Baserow with {exception}. The failure itself "
                                "is not logged: it names the address and what "
                                "was sent with it.",
                                action_id=workflow_action.id,
                                field_id=field.id,
                                exception=type(exc).__name__,
                            )
                        else:
                            logger.opt(exception=exc).error(
                                "Workflow action {action_id} of button field "
                                "{field_id} failed while dispatching.",
                                action_id=workflow_action.id,
                                field_id=field.id,
                            )
                        if names_an_address:
                            # Where the request was going is for whoever
                            # configured the button, not for whoever clicked
                            # it, so the clicker gets the position and a
                            # message of our own. Checked before the user
                            # facing exceptions below, which a refused
                            # connection is one of.
                            raise WorkflowActionDispatchError(
                                workflow_action.id,
                                EXTERNAL_DISPATCH_FAILED_MESSAGE,
                                positions[workflow_action.id],
                                completed=[
                                    positions[done.workflow_action.id]
                                    for done in dispatched
                                ],
                            ) from exc
                        if isinstance(exc, USER_FACING_DISPATCH_EXCEPTIONS):
                            raise WorkflowActionDispatchError(
                                workflow_action.id,
                                str(exc),
                                positions[workflow_action.id],
                                completed=[
                                    positions[done.workflow_action.id]
                                    for done in dispatched
                                ],
                            ) from exc
                        raise exc
                    if may_configure:
                        self._remember_result_shape(workflow_action, result)

                    dispatched.append(DispatchedWorkflowAction(workflow_action, result))

            return WorkflowActionsDispatchResult(dispatched, client_actions, positions)
