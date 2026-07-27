from typing import List

from django.contrib.auth.models import AbstractUser

from baserow.contrib.database.fields.models import ButtonField
from baserow.contrib.database.fields.operations import (
    ReadFieldOperationType,
    UpdateFieldOperationType,
)
from baserow.contrib.database.workflow_actions.handler import (
    DatabaseWorkflowActionHandler,
)
from baserow.contrib.database.workflow_actions.models import DatabaseWorkflowAction
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
from baserow.core.handler import CoreHandler


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
