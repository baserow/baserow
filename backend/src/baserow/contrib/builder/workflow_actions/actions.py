from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.contrib.builder.action_scopes import (
    PageActionScopeType,
    SharedPageActionScopeType,
)
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.handler import (
    BuilderWorkflowActionHandler,
)
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.contrib.builder.workflow_actions.registries import (
    BuilderWorkflowActionType,
)
from baserow.contrib.builder.workflow_actions.service import (
    BuilderWorkflowActionService,
)
from baserow.contrib.builder.workflow_actions.trash_types import (
    BuilderWorkflowActionTrashableItemType,
)
from baserow.core.action.models import Action
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionTypeDescription,
    UndoableActionType,
)
from baserow.core.trash.handler import TrashHandler

WORKFLOW_ACTION_ACTION_CONTEXT = _(
    'of page (%(page_id)s) in builder "%(builder_name)s" (%(builder_id)s).'
)


def workflow_action_action_scope(page: Page) -> ActionScopeStr:
    """
    Returns the undo/redo scope for an action on a workflow action living on ``page``.

    Workflow actions on the builder's shared page are scoped to that shared page so
    they stay undoable from whichever content page the user is editing. Regular
    workflow actions are scoped to their own content page.
    """

    if page.shared:
        return SharedPageActionScopeType.value(page.id)
    return PageActionScopeType.value(page.id)


class CreateBuilderWorkflowActionActionType(UndoableActionType):
    type = "create_builder_workflow_action"
    description = ActionTypeDescription(
        _("Create workflow action"),
        _("Workflow action (%(workflow_action_id)s) created"),
        WORKFLOW_ACTION_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        builder_id: int
        builder_name: str
        page_id: int
        workflow_action_id: int
        workflow_action_type: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workflow_action_type: BuilderWorkflowActionType,
        page: Page,
        **kwargs,
    ) -> BuilderWorkflowAction:
        workflow_action = BuilderWorkflowActionService().create_workflow_action(
            user, workflow_action_type, page, **kwargs
        )

        builder = page.builder
        cls.register_action(
            user=user,
            params=cls.Params(
                builder.id,
                builder.name,
                page.id,
                workflow_action.id,
                workflow_action_type.type,
            ),
            scope=cls.scope(page),
            workspace=builder.workspace,
        )
        return workflow_action

    @classmethod
    def scope(cls, page: Page) -> ActionScopeStr:
        return workflow_action_action_scope(page)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        workflow_action = BuilderWorkflowActionHandler().get_workflow_action(
            params.workflow_action_id
        )
        BuilderWorkflowActionService().delete_workflow_action(user, workflow_action)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        TrashHandler.restore_item(
            user,
            BuilderWorkflowActionTrashableItemType.type,
            params.workflow_action_id,
        )


class UpdateBuilderWorkflowActionActionType(UndoableActionType):
    type = "update_builder_workflow_action"
    description = ActionTypeDescription(
        _("Update workflow action"),
        _("Workflow action (%(workflow_action_id)s) updated"),
        WORKFLOW_ACTION_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        builder_id: int
        builder_name: str
        page_id: int
        workflow_action_id: int
        original_values: Dict[str, Any]
        new_values: Dict[str, Any]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workflow_action: BuilderWorkflowAction,
        **kwargs,
    ) -> BuilderWorkflowAction:
        updated = BuilderWorkflowActionService().update_workflow_action(
            user, workflow_action, **kwargs
        )

        page = updated.workflow_action.page
        builder = page.builder
        cls.register_action(
            user=user,
            params=cls.Params(
                builder.id,
                builder.name,
                page.id,
                updated.workflow_action.id,
                updated.original_values,
                updated.new_values,
            ),
            scope=cls.scope(page),
            workspace=builder.workspace,
        )
        return updated.workflow_action

    @classmethod
    def scope(cls, page: Page) -> ActionScopeStr:
        return workflow_action_action_scope(page)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        workflow_action = BuilderWorkflowActionHandler().get_workflow_action(
            params.workflow_action_id
        )
        BuilderWorkflowActionService().update_workflow_action(
            user, workflow_action, **params.original_values
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        workflow_action = BuilderWorkflowActionHandler().get_workflow_action(
            params.workflow_action_id
        )
        BuilderWorkflowActionService().update_workflow_action(
            user, workflow_action, **params.new_values
        )


class DeleteBuilderWorkflowActionActionType(UndoableActionType):
    type = "delete_builder_workflow_action"
    description = ActionTypeDescription(
        _("Delete workflow action"),
        _("Workflow action (%(workflow_action_id)s) deleted"),
        WORKFLOW_ACTION_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        builder_id: int
        builder_name: str
        page_id: int
        workflow_action_id: int

    @classmethod
    def do(cls, user: AbstractUser, workflow_action: BuilderWorkflowAction) -> None:
        page = workflow_action.page
        builder = page.builder
        # Captured before the workflow action is trashed.
        params = cls.Params(
            builder.id,
            builder.name,
            page.id,
            workflow_action.id,
        )

        BuilderWorkflowActionService().delete_workflow_action(user, workflow_action)

        cls.register_action(
            user=user,
            params=params,
            scope=cls.scope(page),
            workspace=builder.workspace,
        )

    @classmethod
    def scope(cls, page: Page) -> ActionScopeStr:
        return workflow_action_action_scope(page)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        TrashHandler.restore_item(
            user,
            BuilderWorkflowActionTrashableItemType.type,
            params.workflow_action_id,
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        workflow_action = BuilderWorkflowActionHandler().get_workflow_action(
            params.workflow_action_id
        )
        BuilderWorkflowActionService().delete_workflow_action(user, workflow_action)


class OrderBuilderWorkflowActionsActionType(UndoableActionType):
    type = "order_builder_workflow_actions"
    description = ActionTypeDescription(
        _("Order workflow actions"),
        _("Workflow actions ordered"),
        WORKFLOW_ACTION_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        builder_id: int
        builder_name: str
        page_id: int
        element_id: Optional[int]
        workflow_action_ids: List[int]
        original_workflow_action_ids: List[int]

    @classmethod
    def _current_order(cls, page: Page, element: Optional[Element]) -> List[int]:
        return list(
            BuilderWorkflowAction.objects.filter(page=page, element=element)
            .order_by("order", "id")
            .values_list("id", flat=True)
        )

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        page: Page,
        order: List[int],
        element: Optional[Element] = None,
    ) -> None:
        original_order = cls._current_order(page, element)

        BuilderWorkflowActionService().order_workflow_actions(
            user, page, order, element=element
        )

        builder = page.builder
        cls.register_action(
            user=user,
            params=cls.Params(
                builder.id,
                builder.name,
                page.id,
                element.id if element else None,
                order,
                original_order,
            ),
            scope=cls.scope(page),
            workspace=builder.workspace,
        )

    @classmethod
    def scope(cls, page: Page) -> ActionScopeStr:
        return workflow_action_action_scope(page)

    @classmethod
    def _order(cls, user: AbstractUser, params: Params, order: List[int]):
        from baserow.contrib.builder.pages.handler import PageHandler

        page = PageHandler().get_page(params.page_id)
        element = (
            ElementHandler().get_element(params.element_id)
            if params.element_id is not None
            else None
        )
        BuilderWorkflowActionService().order_workflow_actions(
            user, page, order, element=element
        )

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        cls._order(user, params, params.original_workflow_action_ids)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        cls._order(user, params, params.workflow_action_ids)
