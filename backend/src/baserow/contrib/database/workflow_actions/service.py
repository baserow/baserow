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
            # Polymorphism makes a type change a delete plus a create. Deleting
            # first lets the `pre_delete` receiver dispose of the old service.
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
        :return: The (action, result) pairs for the server-side actions, and the
            frontend-only actions for the caller to run itself, both in order.
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
            return [], []

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

        # Nothing server side means no state to protect, so no lock: a button
        # that only opens a URL must not reject a second click.
        if not server_actions:
            return [], client_actions

        # `cache.add` is atomic and only succeeds when the key is absent, so a
        # double click cannot run the sequence twice. Keyed on field and row
        # together, so two buttons on one row do not block each other.
        lock_key = f"button_dispatch_{field.id}_{row.id}"
        # Identifies this click, so the release below knows its own lock.
        lock_token = uuid4().hex
        if not cache.add(
            lock_key,
            lock_token,
            timeout=settings.DATABASE_BUTTON_DISPATCH_LOCK_TTL_SECONDS,
        ):
            raise WorkflowActionDispatchInProgress()

        # Positions come from the whole list, frontend-only actions included, so
        # they match what the clicker counts in the editor.
        positions = {
            workflow_action.id: index
            for index, workflow_action in enumerate(workflow_actions, start=1)
        }

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
                        if isinstance(exc, USER_FACING_DISPATCH_EXCEPTIONS):
                            raise WorkflowActionDispatchError(
                                workflow_action.id,
                                str(exc),
                                positions[workflow_action.id],
                            ) from exc
                        raise
                    results.append((workflow_action, result))

            return results, client_actions
        finally:
            # Only delete this click's own lock: once the TTL expires the key
            # can belong to a later click. Not atomic, but a much smaller
            # window than deleting unconditionally.
            if cache.get(lock_key) == lock_token:
                cache.delete(lock_key)
