from dataclasses import dataclass
from typing import Any, Dict, List

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.contrib.database.action.scopes import (
    TABLE_ACTION_CONTEXT,
    TableActionScopeType,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import ButtonField
from baserow.contrib.database.workflow_actions.handler import (
    DatabaseWorkflowActionHandler,
)
from baserow.contrib.database.workflow_actions.models import DatabaseWorkflowAction
from baserow.contrib.database.workflow_actions.registries import (
    DatabaseWorkflowActionType,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.contrib.database.workflow_actions.trash_types import (
    DatabaseWorkflowActionTrashableItemType,
)
from baserow.core.action.models import Action
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionTypeDescription,
    UndoableActionType,
)
from baserow.core.trash.handler import TrashHandler


def workflow_action_action_scope(field: ButtonField) -> ActionScopeStr:
    """
    The same scope as a field update, so undoing a save that changed the field
    and its actions walks one stack rather than two.
    """

    return TableActionScopeType.value(field.table_id)


class CreateDatabaseWorkflowActionActionType(UndoableActionType):
    type = "create_database_workflow_action"
    description = ActionTypeDescription(
        _("Create button action"),
        _(
            'Action (%(workflow_action_id)s) created on button field "%(field_name)s" '
            "(%(field_id)s)"
        ),
        TABLE_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        database_id: int
        database_name: str
        table_id: int
        table_name: str
        field_id: int
        field_name: str
        workflow_action_id: int
        workflow_action_type: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workflow_action_type: DatabaseWorkflowActionType,
        field: ButtonField,
        **kwargs,
    ) -> DatabaseWorkflowAction:
        workflow_action = DatabaseWorkflowActionService().create_workflow_action(
            user, workflow_action_type, field, **kwargs
        )

        table = field.table
        database = table.database
        cls.register_action(
            user=user,
            params=cls.Params(
                database.id,
                database.name,
                table.id,
                table.name,
                field.id,
                field.name,
                workflow_action.id,
                workflow_action_type.type,
            ),
            scope=cls.scope(field),
            workspace=database.workspace,
        )
        return workflow_action

    @classmethod
    def scope(cls, field: ButtonField) -> ActionScopeStr:
        return workflow_action_action_scope(field)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        workflow_action = DatabaseWorkflowActionHandler().get_workflow_action(
            params.workflow_action_id
        )
        DatabaseWorkflowActionService().delete_workflow_action(user, workflow_action)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        TrashHandler.restore_item(
            user,
            DatabaseWorkflowActionTrashableItemType.type,
            params.workflow_action_id,
        )


class UpdateDatabaseWorkflowActionActionType(UndoableActionType):
    """
    Replays the values the service captured around the update. They leave out
    whatever the backing service calls sensitive, so undo and redo leave those
    fields as they are.
    """

    type = "update_database_workflow_action"
    description = ActionTypeDescription(
        _("Update button action"),
        _(
            'Action (%(workflow_action_id)s) updated on button field "%(field_name)s" '
            "(%(field_id)s)"
        ),
        TABLE_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        database_id: int
        database_name: str
        table_id: int
        table_name: str
        field_id: int
        field_name: str
        workflow_action_id: int
        original_values: Dict[str, Any]
        new_values: Dict[str, Any]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workflow_action: DatabaseWorkflowAction,
        **kwargs,
    ) -> DatabaseWorkflowAction:
        updated = DatabaseWorkflowActionService().update_workflow_action(
            user, workflow_action, **kwargs
        )

        field = updated.workflow_action.field
        table = field.table
        database = table.database
        cls.register_action(
            user=user,
            params=cls.Params(
                database.id,
                database.name,
                table.id,
                table.name,
                field.id,
                field.name,
                updated.workflow_action.id,
                updated.original_values,
                updated.new_values,
            ),
            scope=cls.scope(field),
            workspace=database.workspace,
        )
        return updated.workflow_action

    @classmethod
    def scope(cls, field: ButtonField) -> ActionScopeStr:
        return workflow_action_action_scope(field)

    @classmethod
    def _update(cls, user: AbstractUser, params: Params, values: Dict[str, Any]):
        # Locked, as the API does, since the values can carry a type change.
        workflow_action = (
            DatabaseWorkflowActionHandler().get_workflow_action_for_update(
                params.workflow_action_id
            )
        )
        DatabaseWorkflowActionService().update_workflow_action(
            user, workflow_action, **values
        )

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        cls._update(user, params, params.original_values)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        cls._update(user, params, params.new_values)


class DeleteDatabaseWorkflowActionActionType(UndoableActionType):
    type = "delete_database_workflow_action"
    description = ActionTypeDescription(
        _("Delete button action"),
        _(
            'Action (%(workflow_action_id)s) deleted from button field "%(field_name)s" '
            "(%(field_id)s)"
        ),
        TABLE_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        database_id: int
        database_name: str
        table_id: int
        table_name: str
        field_id: int
        field_name: str
        workflow_action_id: int

    @classmethod
    def do(cls, user: AbstractUser, workflow_action: DatabaseWorkflowAction) -> None:
        field = workflow_action.field
        table = field.table
        database = table.database
        params = cls.Params(
            database.id,
            database.name,
            table.id,
            table.name,
            field.id,
            field.name,
            workflow_action.id,
        )

        DatabaseWorkflowActionService().delete_workflow_action(user, workflow_action)

        cls.register_action(
            user=user,
            params=params,
            scope=cls.scope(field),
            workspace=database.workspace,
        )

    @classmethod
    def scope(cls, field: ButtonField) -> ActionScopeStr:
        return workflow_action_action_scope(field)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        TrashHandler.restore_item(
            user,
            DatabaseWorkflowActionTrashableItemType.type,
            params.workflow_action_id,
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        workflow_action = DatabaseWorkflowActionHandler().get_workflow_action(
            params.workflow_action_id
        )
        DatabaseWorkflowActionService().delete_workflow_action(user, workflow_action)


class OrderDatabaseWorkflowActionsActionType(UndoableActionType):
    type = "order_database_workflow_actions"
    description = ActionTypeDescription(
        _("Order button actions"),
        _('Actions ordered on button field "%(field_name)s" (%(field_id)s)'),
        TABLE_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        database_id: int
        database_name: str
        table_id: int
        table_name: str
        field_id: int
        field_name: str
        workflow_action_ids: List[int]
        original_workflow_action_ids: List[int]

    @classmethod
    def do(cls, user: AbstractUser, field: ButtonField, order: List[int]) -> List[int]:
        original_order = list(
            DatabaseWorkflowAction.objects.filter(field=field)
            .order_by("order", "id")
            .values_list("id", flat=True)
        )

        full_order = DatabaseWorkflowActionService().order_workflow_actions(
            user, field, order
        )

        table = field.table
        database = table.database
        cls.register_action(
            user=user,
            params=cls.Params(
                database.id,
                database.name,
                table.id,
                table.name,
                field.id,
                field.name,
                full_order,
                original_order,
            ),
            scope=cls.scope(field),
            workspace=database.workspace,
        )
        return full_order

    @classmethod
    def scope(cls, field: ButtonField) -> ActionScopeStr:
        return workflow_action_action_scope(field)

    @classmethod
    def _order(cls, user: AbstractUser, params: Params, order: List[int]):
        field = FieldHandler().get_field(
            params.field_id, base_queryset=ButtonField.objects
        )
        DatabaseWorkflowActionService().order_workflow_actions(user, field, order)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        cls._order(user, params, params.original_workflow_action_ids)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        cls._order(user, params, params.workflow_action_ids)
