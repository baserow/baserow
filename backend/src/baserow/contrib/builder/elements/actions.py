from dataclasses import dataclass
from typing import Any, Dict

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.contrib.builder.action_scopes import (
    ELEMENT_ACTION_CONTEXT,
    PageActionScopeType,
    SharedPageActionScopeType,
)
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.elements.registries import ElementType
from baserow.contrib.builder.elements.service import ElementService
from baserow.contrib.builder.elements.trash_types import ElementTrashableItemType
from baserow.contrib.builder.elements.types import ElementsAndWorkflowActions
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page
from baserow.core.action.models import Action
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionTypeDescription,
    UndoableActionType,
)
from baserow.core.graph.types import GraphPointPositionType
from baserow.core.trash.handler import TrashHandler


def element_action_scope(page: Page) -> ActionScopeStr:
    """
    Returns the undo/redo scope for an action on an element living on ``page``.

    Elements on the builder's shared page (header/footer elements and their
    children) are scoped to that shared page so they stay undoable from whichever
    content page the user is editing. Regular elements are scoped to their own
    content page.
    """

    if page.shared:
        return SharedPageActionScopeType.value(page.id)
    return PageActionScopeType.value(page.id)


class CreateElementActionType(UndoableActionType):
    type = "create_element"
    description = ActionTypeDescription(
        _("Create element"),
        _("Element (%(element_id)s) created"),
        ELEMENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        builder_id: int
        builder_name: str
        page_id: int
        element_id: int
        element_type: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        element_type: ElementType,
        page: Page,
        data: dict,
    ) -> Element:
        element = ElementService().create_element(user, element_type, page, **data)

        builder = page.builder
        cls.register_action(
            user=user,
            params=cls.Params(
                builder.id,
                builder.name,
                page.id,
                element.id,
                element.get_type().type,
            ),
            scope=cls.scope(page),
            workspace=builder.workspace,
        )
        return element

    @classmethod
    def scope(cls, page: Page):
        return element_action_scope(page)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        element = ElementHandler().get_element_for_update(params.element_id)
        ElementService().delete_element(user, element)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        TrashHandler.restore_item(
            user,
            ElementTrashableItemType.type,
            params.element_id,
        )


class UpdateElementActionType(UndoableActionType):
    type = "update_element"
    description = ActionTypeDescription(
        _("Update element"),
        _("Element (%(element_id)s) updated"),
        ELEMENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        builder_id: int
        builder_name: str
        page_id: int
        element_id: int
        element_type: str
        element_original_params: Dict[str, Any]
        element_new_params: Dict[str, Any]

    @classmethod
    def do(cls, user: AbstractUser, element: Element, new_data: dict) -> Element:
        updated = ElementService().update_element(user, element, **new_data)

        builder = updated.element.page.builder
        cls.register_action(
            user=user,
            params=cls.Params(
                builder.id,
                builder.name,
                updated.element.page_id,
                updated.element.id,
                updated.element.get_type().type,
                updated.original_values,
                updated.new_values,
            ),
            scope=cls.scope(updated.element.page),
            workspace=builder.workspace,
        )
        return updated.element

    @classmethod
    def scope(cls, page: Page):
        return element_action_scope(page)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        element = ElementHandler().get_element_for_update(params.element_id)
        ElementService().update_element(user, element, **params.element_original_params)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        element = ElementHandler().get_element_for_update(params.element_id)
        ElementService().update_element(user, element, **params.element_new_params)


class DeleteElementActionType(UndoableActionType):
    type = "delete_element"
    description = ActionTypeDescription(
        _("Delete element"),
        _("Element (%(element_id)s) deleted"),
        ELEMENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        builder_id: int
        builder_name: str
        page_id: int
        element_id: int
        element_type: str

    @classmethod
    def do(cls, user: AbstractUser, element: Element) -> None:
        page = element.page
        builder = page.builder
        # Captured before the element is trashed and removed from the graph.
        params = cls.Params(
            builder.id,
            builder.name,
            page.id,
            element.id,
            element.get_type().type,
        )

        ElementService().delete_element(user, element)

        cls.register_action(
            user=user,
            params=params,
            scope=cls.scope(page),
            workspace=builder.workspace,
        )

    @classmethod
    def scope(cls, page: Page):
        return element_action_scope(page)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        TrashHandler.restore_item(
            user,
            ElementTrashableItemType.type,
            params.element_id,
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        element = ElementHandler().get_element_for_update(params.element_id)
        ElementService().delete_element(user, element)


class DuplicateElementActionType(UndoableActionType):
    type = "duplicate_element"
    description = ActionTypeDescription(
        _("Duplicate element"),
        _("Element (%(element_id)s) duplicated"),
        ELEMENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        builder_id: int
        builder_name: str
        page_id: int
        element_id: int  # The source element id
        element_type: str  # The source element type
        duplicated_element_id: int

    @classmethod
    def do(cls, user: AbstractUser, element: Element) -> ElementsAndWorkflowActions:
        page = element.page
        builder = page.builder

        result = ElementService().duplicate_element(user, element)
        # The handler returns the duplicated root element first, followed by its
        # children (see ElementHandler._duplicate_element_recursive).
        duplicated_root = result["elements"][0]

        cls.register_action(
            user=user,
            params=cls.Params(
                builder.id,
                builder.name,
                page.id,
                element.id,
                element.get_type().type,
                duplicated_root.id,
            ),
            scope=cls.scope(page),
            workspace=builder.workspace,
        )
        return result

    @classmethod
    def scope(cls, page: Page):
        return element_action_scope(page)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        # Trash the duplicated element (its children cascade with it).
        element = ElementHandler().get_element_for_update(params.duplicated_element_id)
        ElementService().delete_element(user, element)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        TrashHandler.restore_item(
            user,
            ElementTrashableItemType.type,
            params.duplicated_element_id,
        )


class MoveElementActionType(UndoableActionType):
    type = "move_element"
    description = ActionTypeDescription(
        _("Move element"),
        _("Element (%(element_id)s) moved"),
        ELEMENT_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        builder_id: int
        builder_name: str
        page_id: int  # The source page id, used as the undo/redo scope.
        element_id: int
        element_type: str
        origin_page_id: int
        origin_reference_element_id: int | None
        origin_position: GraphPointPositionType
        origin_place_in_container: str
        destination_page_id: int
        destination_reference_element_id: int | None
        destination_position: GraphPointPositionType
        destination_place_in_container: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        element: Element,
        target_page: Page,
        place_in_container: str,
        reference_element_id: int | None,
        position: GraphPointPositionType,
    ) -> Element:
        # Captured before the move reassigns element.page. Cross-page moves are
        # scoped to the source page (the page the user acted from).
        source_page = element.page
        source_page_id = source_page.id

        move = ElementService().move_element(
            user,
            target_page,
            element,
            place_in_container=place_in_container,
            reference_element_id=reference_element_id,
            position=position,
        )

        builder = target_page.builder
        cls.register_action(
            user=user,
            params=cls.Params(
                builder.id,
                builder.name,
                source_page_id,
                move.element.id,
                move.element.get_type().type,
                source_page_id,
                move.previous_reference_element.id
                if move.previous_reference_element
                else None,
                move.previous_position,
                move.previous_output,
                target_page.id,
                reference_element_id,
                position,
                place_in_container,
            ),
            scope=cls.scope(source_page),
            workspace=builder.workspace,
        )
        return move.element

    @classmethod
    def scope(cls, page: Page):
        return element_action_scope(page)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        element = ElementHandler().get_element_for_update(params.element_id)
        origin_page = PageHandler().get_page(params.origin_page_id)
        ElementService().move_element(
            user,
            origin_page,
            element,
            place_in_container=params.origin_place_in_container,
            reference_element_id=params.origin_reference_element_id,
            position=params.origin_position,
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        element = ElementHandler().get_element_for_update(params.element_id)
        destination_page = PageHandler().get_page(params.destination_page_id)
        ElementService().move_element(
            user,
            destination_page,
            element,
            place_in_container=params.destination_place_in_container,
            reference_element_id=params.destination_reference_element_id,
            position=params.destination_position,
        )
