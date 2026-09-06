import json
from dataclasses import fields as dataclass_fields
from typing import Any, Callable, List, Optional

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.db import transaction

from loguru import logger
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
from baserow.contrib.database.workflow_actions.models import DatabaseWorkflowAction
from baserow.contrib.database.workflow_actions.operations import (
    DispatchDatabaseWorkflowActionOperationType,
)
from baserow.contrib.database.workflow_actions.registries import (
    DatabaseWorkflowActionType,
    database_workflow_action_type_registry,
)
from baserow.contrib.database.workflow_actions.signals import (
    workflow_action_created,
    workflow_action_deleted,
    workflow_action_updated,
    workflow_actions_reordered,
)
from baserow.contrib.database.workflow_actions.types import (
    DispatchedWorkflowAction,
    WorkflowActionsDispatchResult,
)
from baserow.core.action.context import without_undo_redo_registration
from baserow.core.handler import CoreHandler
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.services.exceptions import (
    AddressNotAllowedDispatchException,
    DoesNotExist,
    InvalidContextContentDispatchException,
    InvalidContextDispatchException,
    PermissionDeniedDispatchException,
    RemoteRefusedDispatchException,
    ResponseTooLargeDispatchException,
    ServiceImproperlyConfiguredDispatchException,
    TriggerServiceNotDispatchable,
    UnexpectedDispatchException,
    UnreachableAddressDispatchException,
)
from baserow.core.services.models import Service
from baserow.core.services.types import DispatchResult
from baserow.core.types import PermissionCheck

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

# Failures a service raises before it can send anything: a formula it could not
# resolve, or a body it refused to build. Nothing left the instance, so a click
# that ends on one of these is not charged for outbound traffic.
DID_NOT_REACH_OUT_EXCEPTIONS = (
    InvalidContextDispatchException,
    InvalidContextContentDispatchException,
    ServiceImproperlyConfiguredDispatchException,
    # The address itself was refused, by Advocate rather than by the endpoint,
    # so nothing was sent even though the message names where it was going.
    AddressNotAllowedDispatchException,
)


def reached_outside(exc: Exception) -> bool:
    """
    Whether a failed external action had already sent its request.

    :param exc: What the action failed with.
    :return: True when the request went out, so the click owes for it.
    """

    # Subclasses of the failures above, but raised once the instance had
    # already reached out, so they are charged like any other.
    if isinstance(
        exc,
        (
            ResponseTooLargeDispatchException,
            UnreachableAddressDispatchException,
            RemoteRefusedDispatchException,
        ),
    ):
        return True

    return not isinstance(exc, DID_NOT_REACH_OUT_EXCEPTIONS)


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

        return list(self.handler.get_workflow_actions(field))

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
        self, user: AbstractUser, workflow_action: DatabaseWorkflowAction, **kwargs
    ) -> DatabaseWorkflowAction:
        field = workflow_action.field
        CoreHandler().check_permissions(
            user,
            UpdateFieldOperationType.type,
            workspace=field.table.database.workspace,
            context=field,
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
                workflow_action, workflow_action_type, **prepared_values
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

        workflow_action_id = workflow_action.id
        self.handler.delete_workflow_action(workflow_action)

        workflow_action_deleted.send(
            self, workflow_action_id=workflow_action_id, field=field, user=user
        )

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

    def dispatch_workflow_actions(
        self,
        user: AbstractUser,
        field: ButtonField,
        row: Any,
        workflow_actions: Optional[List[DatabaseWorkflowAction]] = None,
        on_external_dispatch: Optional[Callable[[DatabaseWorkflowAction], None]] = None,
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
        :param on_external_dispatch: Called just before each action that
            reaches outside Baserow, so the caller learns what the click really
            sent rather than what the button is configured to send.
        :raises WorkflowActionDispatchInProgress: When a click is already running
            for this field and row.
        :raises WorkflowActionDispatchError: When an action fails with a message
            meant for the clicker. Any other failure is re-raised as it is, so
            its message stays server side. Either way the actions before it have
            already run and are not rolled back.
        :return: What the server-side actions returned, and the frontend-only
            actions for the caller to run itself, both in order.
        """

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

        if not workflow_actions:
            return WorkflowActionsDispatchResult()

        # Checked over every action, frontend-only included, so a click is
        # refused as a whole (ADR 006 section 7), and before the lock is taken,
        # so a refused user never holds it.
        CoreHandler().check_multiple_permissions(
            [
                PermissionCheck(
                    user,
                    DispatchDatabaseWorkflowActionOperationType.type,
                    workflow_action,
                )
                for workflow_action in workflow_actions
            ],
            workspace=field.table.database.workspace,
            raise_exception=True,
        )

        # Refused as a whole: a sequence that cannot finish should not start.
        # After the permission check, since the reason describes how this
        # installation is configured and only a dispatcher may see it. Once per
        # type, since it is the type that is unavailable rather than the
        # action, and in the order the actions run, so a button carrying two of
        # them names the same one every time.
        checked_types = {}
        for workflow_action in workflow_actions:
            workflow_action_type = workflow_action.get_type()
            checked_types.setdefault(workflow_action_type.type, workflow_action_type)
        for workflow_action_type in checked_types.values():
            workflow_action_type.raise_if_deactivated(field.table.database.workspace)

        # Frontend-only actions can't be dispatched here; the caller runs them
        # in the browser.
        client_actions = [
            wa for wa in workflow_actions if wa.get_type().is_frontend_only
        ]
        server_actions = [
            wa for wa in workflow_actions if not wa.get_type().is_frontend_only
        ]

        # Positions come from the whole list, frontend-only actions included, so
        # they match what the clicker counts in the editor. Taken from the
        # execution order rather than from `order`, which two actions can share.
        positions = {
            workflow_action.id: index
            for index, workflow_action in enumerate(workflow_actions, start=1)
        }

        # Nothing server side means no state to protect, so no lock: a button
        # that only opens a URL must not reject a second click.
        if not server_actions:
            return WorkflowActionsDispatchResult(
                client_actions=client_actions, positions=positions
            )

        # Taken only when the key is absent, so a double click cannot run the
        # sequence twice, and released by a script that checks ownership first,
        # so a click whose TTL ran out cannot drop a later click's lock. Keyed
        # on field and row together, so two buttons on one row do not block
        # each other.
        # Resolved once for both: `specific` caches on the instance, but only
        # while these are the objects the dispatch goes on to use.
        services = [
            workflow_action.service.specific for workflow_action in server_actions
        ]
        # Before the lock: it holds nothing the lock protects.
        self._resolve_integrations(services)

        lock = cache.lock(
            f"button_dispatch_{field.id}_{row.id}",
            timeout=self._lock_ttl_for(server_actions, services),
        )
        # Never waits: a second click is refused rather than queued behind one
        # that is still running.
        if not lock.acquire(blocking=False):
            raise WorkflowActionDispatchInProgress()

        try:
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
                    # Each action reads the clicked row itself, so it sees what
                    # the actions before it did to it (ADR 006 section 4).
                    dispatch_context.start_action()
                    is_external = workflow_action.get_type().is_external
                    try:
                        result = self.handler.dispatch_workflow_action(
                            workflow_action, dispatch_context
                        )
                    except Exception as exc:
                        if (
                            is_external
                            and on_external_dispatch
                            and reached_outside(exc)
                        ):
                            on_external_dispatch(workflow_action)
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
                            logger.exception(
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
                            ) from exc
                        if isinstance(exc, USER_FACING_DISPATCH_EXCEPTIONS):
                            raise WorkflowActionDispatchError(
                                workflow_action.id,
                                str(exc),
                                positions[workflow_action.id],
                            ) from exc
                        raise
                    if is_external and on_external_dispatch:
                        on_external_dispatch(workflow_action)
                    if may_configure:
                        self._remember_result_shape(workflow_action, result)

                    dispatched.append(DispatchedWorkflowAction(workflow_action, result))

            return WorkflowActionsDispatchResult(dispatched, client_actions, positions)
        finally:
            try:
                lock.release()
            except LockNotOwnedError:
                # The TTL ran out mid-sequence, so the key is a later click's
                # to release.
                pass
