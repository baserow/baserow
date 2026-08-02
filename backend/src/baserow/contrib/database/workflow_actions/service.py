from typing import Any, List, Tuple
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.cache import cache

from loguru import logger

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

# Dispatch failures whose message is written for the person who clicked, and so
# is safe to hand back in the API response. Anything else, such as a
# `DatabaseError`, a `PermissionException` or an internal `ValueError`, keeps
# its message server side and reaches the generic 500 handler untouched.
# `UnexpectedDispatchException` is deliberately left out: by definition it wraps
# an error nobody anticipated, and its message is that error's own text.
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
        CoreHandler().check_permissions(
            user,
            ReadFieldOperationType.type,
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
            # Polymorphism makes a type change a delete plus a create. The old
            # action is removed first so its `pre_delete` receiver disposes of
            # the old service, and `prepare_values` runs without an instance so
            # a fresh service of the new type is built. `field` and `order` are
            # not in the payload, so they are carried over from the old action.
            workflow_action_type = database_workflow_action_type_registry.get(
                kwargs["type"]
            )
            order = workflow_action.order
            self.handler.delete_workflow_action(workflow_action)
            prepared_values = workflow_action_type.prepare_values(kwargs, user)
            prepared_values["field"] = field
            prepared_values["order"] = order
            workflow_action = self.handler.create_workflow_action(
                workflow_action_type, **prepared_values
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
    ):
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

    def dispatch_workflow_actions(
        self, user: AbstractUser, field: ButtonField, row: Any
    ) -> Tuple[
        List[Tuple[DatabaseWorkflowAction, DispatchResult]],
        List[DatabaseWorkflowAction],
    ]:
        """
        Runs a button field's server-side actions in order, as the given user,
        and hands back its frontend-only actions, such as `open_url`, for the
        caller to run instead. `DatabaseWorkflowActionType.dispatch` raises for
        a frontend-only action, so the loop below must never reach one.

        Deliberately not wrapped in a transaction: ADR 006 section 3 requires
        completed actions to stay when a later one fails, because a sequence can
        contain irreversible effects, such as a sent email, that no rollback can
        take back. Undoing the rows while leaving the irreversible effects
        standing would leave the sequence half applied in a way the user cannot
        see. Each action keeps whatever atomicity its own handler already has.

        Each result is paired with the action that produced it, in the same
        step, rather than left for a caller to re-fetch and re-align. A
        caller re-fetching the actions afterwards would run against a
        separate, unsynchronised query, which can drift from this one if the
        field's actions change between the two reads.

        :param user: The user who clicked.
        :param field: The clicked button field.
        :param row: The clicked row.
        :raises WorkflowActionDispatchInProgress: When a click is already running
            for this field and row.
        :raises WorkflowActionDispatchError: When an action fails with a message
            meant for the clicker. Any other failure is re-raised as it is, so
            its message stays server side. Either way the actions before it have
            already run and are not rolled back.
        :return: A pair of: one (action, result) per server-side action, in
            order; and the frontend-only actions, in order, for the caller to
            run itself.
        """

        # Clicking is at least reading the field, and this check is field
        # scoped, so it also covers the case below where there are no actions
        # to check individually. Without it an outsider would get an empty
        # result rather than a refusal, which tells them the field and row
        # exist.
        CoreHandler().check_permissions(
            user,
            ReadFieldOperationType.type,
            workspace=field.table.database.workspace,
            context=field,
        )

        workflow_actions = list(self.handler.get_workflow_actions(field))

        # A button with nothing configured has nothing to run and nothing to
        # lock, so it returns before both.
        if not workflow_actions:
            return [], []

        # The dispatch operation is scoped to the action rather than the field,
        # so every action in the sequence is checked. A role granted on the
        # field covers all of them, which is how "who can click this button"
        # is expressed today (ADR 006 section 7). Deliberately checked before
        # the lock is taken, so a refused user never holds it at all. Checked
        # over every action, frontend-only included, so clicking is refused as
        # a whole rather than only for the actions the server would run.
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

        # `DatabaseWorkflowActionType.dispatch` raises for a frontend-only
        # action, so those never reach the loop below; the caller runs them in
        # the browser instead.
        client_actions = [
            wa for wa in workflow_actions if wa.get_type().is_frontend_only
        ]
        server_actions = [
            wa for wa in workflow_actions if not wa.get_type().is_frontend_only
        ]

        # Nothing to run server side means nothing to serialise a click
        # against: taking the lock would reject a second click on a button
        # that only opens a URL, which has no state to protect.
        if not server_actions:
            return [], client_actions

        # `cache.add` is atomic on the Redis-backed cache and only succeeds when
        # the key is absent, so a double click cannot run the sequence twice.
        # Keyed on the field and row together, so two button fields on one row
        # do not block each other (ADR 006 section 3).
        lock_key = f"button_dispatch_{field.id}_{row.id}"
        # The value identifies this click, so the release below can tell its own
        # lock from one a later click took after this one's TTL expired.
        lock_token = uuid4().hex
        if not cache.add(
            lock_key, lock_token, timeout=settings.BUTTON_DISPATCH_LOCK_TTL_SECONDS
        ):
            raise WorkflowActionDispatchInProgress()

        try:
            dispatch_context = DatabaseDispatchContext(user, field, row)
            results = []

            # The clicker's own actions must not land in their undo stack
            # (ADR 006 section 8), while still firing `action_done`.
            with without_undo_redo_registration(user):
                for workflow_action in server_actions:
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
                        # Only a message meant for the clicker travels back in
                        # the response. Everything else keeps its message on the
                        # server and becomes a plain 500.
                        if isinstance(exc, USER_FACING_DISPATCH_EXCEPTIONS):
                            raise WorkflowActionDispatchError(
                                workflow_action.id, str(exc)
                            ) from exc
                        raise
                    results.append((workflow_action, result))

            return results, client_actions
        finally:
            # Release only this click's own lock. Once the TTL has expired the
            # key can belong to a later click, and deleting that one would let a
            # third click start while the second is still running. The read and
            # the delete are not atomic together, so a lock expiring in the
            # sliver between them can still be deleted by its previous holder;
            # that is a strictly smaller window than deleting unconditionally.
            if cache.get(lock_key) == lock_token:
                cache.delete(lock_key)
