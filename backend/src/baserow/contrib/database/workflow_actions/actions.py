import dataclasses
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.contrib.auth.models import AbstractUser
from django.db.models import Q
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
    database_workflow_action_type_registry,
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
    UndoableActionCustomCleanupMixin,
    UndoableActionType,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
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


class UpdateDatabaseWorkflowActionActionType(
    UndoableActionCustomCleanupMixin, UndoableActionType
):
    """
    Replays the values the service captured around the update. They leave out
    whatever the backing service calls sensitive, so undo and redo leave those
    fields as they are.

    A type change replaces the action's service, and a service built from those
    values would come back with the sensitive fields blank. So the replaced
    service is kept, and undo and redo attach the one each side had. Only their
    ids are logged, and whichever is left unattached is deleted when the action
    is cleaned up.
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
        original_service_id: Optional[int] = None
        new_service_id: Optional[int] = None

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workflow_action: DatabaseWorkflowAction,
        **kwargs,
    ) -> DatabaseWorkflowAction:
        original_service_id = getattr(workflow_action.specific, "service_id", None)
        updated = DatabaseWorkflowActionService().update_workflow_action(
            user, workflow_action, keep_replaced_service=True, **kwargs
        )
        type_changed = updated.original_values["type"] != updated.new_values["type"]

        field = updated.workflow_action.field
        table = field.table
        database = table.database
        params = cls.Params(
            database.id,
            database.name,
            table.id,
            table.name,
            field.id,
            field.name,
            updated.workflow_action.id,
            updated.original_values,
            updated.new_values,
            original_service_id if type_changed else None,
            (
                getattr(updated.workflow_action, "service_id", None)
                if type_changed
                else None
            ),
        )
        if updated.original_values == updated.new_values:
            # Only sensitive fields changed, which an undo leaves as they are,
            # so a step would report an undo that changes nothing. The audit
            # log still hears about the update.
            cls.send_action_done_signal(
                user,
                dataclasses.asdict(params),
                cls.scope(field),
                database.workspace,
            )
        else:
            cls.register_action(
                user=user,
                params=params,
                scope=cls.scope(field),
                workspace=database.workspace,
            )
        return updated.workflow_action

    @classmethod
    def scope(cls, field: ButtonField) -> ActionScopeStr:
        return workflow_action_action_scope(field)

    @classmethod
    def _update(
        cls,
        user: AbstractUser,
        action: Action,
        params: Params,
        values: Dict[str, Any],
        service_id: Optional[int],
        leaving_service_key: str,
    ):
        # Locked, as the API does, since the values can carry a type change.
        workflow_action = (
            DatabaseWorkflowActionHandler().get_workflow_action_for_update(
                params.workflow_action_id
            )
        )
        if values["type"] != workflow_action.get_type().type:
            # The service the action has now is kept for the opposite step. It
            # is not always the one logged: a field type change undone since
            # recreates the action with a copy, which nothing would otherwise
            # name, attach again or clean up. The handler saves the action
            # after this.
            action.params[leaving_service_key] = getattr(
                workflow_action.specific, "service_id", None
            )
            DatabaseWorkflowActionService().restore_workflow_action_type(
                user, workflow_action, values, cls._kept_service(service_id)
            )
        else:
            DatabaseWorkflowActionService().update_workflow_action(
                user, workflow_action, **values
            )

    @classmethod
    def _kept_service(cls, service_id: Optional[int]) -> Optional[Service]:
        if service_id is None:
            return None
        service = Service.objects.filter(id=service_id).first()
        return service.specific if service is not None else None

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        cls._update(
            user,
            action_to_undo,
            params,
            params.original_values,
            params.original_service_id,
            "new_service_id",
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        cls._update(
            user,
            action_to_redo,
            params,
            params.new_values,
            params.new_service_id,
            "original_service_id",
        )

    @classmethod
    def clean_up_any_extra_action_data(cls, action_being_cleaned_up: Action):
        """
        Deletes the services a type change kept, unless an action has one again
        or a later update still names it.
        """

        params = action_being_cleaned_up.params
        for service_id in (
            params.get("original_service_id"),
            params.get("new_service_id"),
        ):
            if service_id is None or cls._service_is_needed(
                service_id, action_being_cleaned_up
            ):
                continue
            service = cls._kept_service(service_id)
            if service is not None:
                ServiceHandler().delete_service(service.get_type(), service)

    @classmethod
    def _service_is_needed(
        cls, service_id: int, action_being_cleaned_up: Action
    ) -> bool:
        attached = any(
            model_class.objects_and_trash.filter(service_id=service_id).exists()
            for model_class in {
                action_type.model_class
                for action_type in database_workflow_action_type_registry.get_all()
            }
            if any(field.name == "service" for field in model_class._meta.fields)
        )
        named_elsewhere = (
            Action.objects.filter(type=cls.type)
            .exclude(id=action_being_cleaned_up.id)
            .filter(
                Q(params__original_service_id=service_id)
                | Q(params__new_service_id=service_id)
            )
            .exists()
        )
        return attached or named_elsewhere


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
