import json
from dataclasses import fields as dataclass_fields
from typing import Any, List

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.cache import cache

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
from baserow.core.services.exceptions import (
    DoesNotExist,
    InvalidContextContentDispatchException,
    InvalidContextDispatchException,
    PermissionDeniedDispatchException,
    ServiceImproperlyConfiguredDispatchException,
    TriggerServiceNotDispatchable,
)
from baserow.core.services.types import DispatchResult
from baserow.core.types import PermissionCheck

# What a failed external action tells the clicker. The service's own message
# names the URL it could not reach, which is where an API key would be.
EXTERNAL_DISPATCH_FAILED_MESSAGE = "the request could not be completed"

# Failures whose message is written for the clicker, and so is safe to return.
# Anything else keeps its message server side.
USER_FACING_DISPATCH_EXCEPTIONS = (
    ServiceImproperlyConfiguredDispatchException,
    InvalidContextDispatchException,
    InvalidContextContentDispatchException,
    PermissionDeniedDispatchException,
    TriggerServiceNotDispatchable,
    DoesNotExist,
)


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

        prepared_values = workflow_action_type.prepare_values(kwargs, user)
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
            prepared_values = workflow_action_type.prepare_values(kwargs, user)
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

        if not workflow_action.get_type().captures_sample_data:
            return

        # An endpoint that answered 404 with an error page, or timed out, still
        # counts as a successful dispatch and describes nothing. Overwriting
        # with it would drop the shape an earlier click learned, and with it
        # every explorer node the actions after this one point at.
        data = result.data if isinstance(result.data, dict) else {}
        status_code = data.get("status_code")
        if not isinstance(status_code, int) or not 200 <= status_code < 300:
            return

        sample_data = {
            f.name: getattr(result, f.name) for f in dataclass_fields(result)
        }

        try:
            encoded = json.dumps(sample_data)

            if (
                len(encoded.encode("utf-8"))
                > settings.DATABASE_BUTTON_SAMPLE_DATA_MAX_BYTES
            ):
                # A big response still reached the clicker; it is only its
                # shape that the editor goes without.
                return

            service = workflow_action.service
            service.sample_data = sample_data
            service.save(update_fields=["sample_data"])
        except Exception:
            # Never fail a click that already succeeded. What an endpoint can
            # answer with is not ours to predict: a NaN or a NUL byte encodes
            # here and is then refused by the column it is written to, and by
            # this point the request has left and earlier actions have already
            # written their rows.
            logger.warning(
                "Could not remember the result of workflow action {action_id}.",
                action_id=workflow_action.id,
            )

    def dispatch_workflow_actions(
        self, user: AbstractUser, field: ButtonField, row: Any
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

        workflow_actions = list(self.handler.get_workflow_actions(field))

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
        lock = cache.lock(
            f"button_dispatch_{field.id}_{row.id}",
            timeout=settings.DATABASE_BUTTON_DISPATCH_LOCK_TTL_SECONDS,
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
                    try:
                        result = self.handler.dispatch_workflow_action(
                            workflow_action, dispatch_context
                        )
                    except Exception as exc:
                        logger.exception(
                            "Workflow action {action_id} of button field "
                            "{field_id} failed while dispatching.",
                            action_id=workflow_action.id,
                            field_id=field.id,
                        )
                        if workflow_action.get_type().is_external:
                            # Where the request went is the clicker's problem
                            # to see, not a server error, but every message the
                            # service writes names the address it failed on,
                            # the URL with its query string included. Checked
                            # before the user facing exceptions below, which is
                            # what some of those failures arrive as. They get
                            # the position and a message of our own instead.
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
