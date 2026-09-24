from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.contrib.builder.handler import BuilderHandler
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.pages.service import PageService
from baserow.contrib.builder.pages.trash_types import PageTrashableItemType
from baserow.contrib.builder.pages.types import PagePathParams, PageQueryParams
from baserow.core.action.models import Action
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionTypeDescription,
    UndoableActionType,
)
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import ChildProgressBuilder, extract_undo_redo_values

PAGE_ACTION_CONTEXT = _('in builder "%(builder_name)s" (%(builder_id)s).')


class CreatePageActionType(UndoableActionType):
    type = "create_page"
    description = ActionTypeDescription(
        _("Create page"),
        _('Page "%(page_name)s" (%(page_id)s) created'),
        PAGE_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        builder_id: int
        builder_name: str
        page_id: int
        page_name: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        builder: Builder,
        name: str,
        path: str,
        path_params: Optional[PagePathParams] = None,
        query_params: Optional[PageQueryParams] = None,
    ) -> Page:
        page = PageService().create_page(
            user,
            builder,
            name,
            path,
            path_params=path_params,
            query_params=query_params,
        )

        cls.register_action(
            user=user,
            params=cls.Params(builder.id, builder.name, page.id, page.name),
            scope=cls.scope(builder.id),
            workspace=builder.workspace,
        )
        return page

    @classmethod
    def scope(cls, builder_id: int) -> ActionScopeStr:
        return ApplicationActionScopeType.value(builder_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        page = PageHandler().get_page(params.page_id)
        PageService().delete_page(user, page)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        TrashHandler.restore_item(user, PageTrashableItemType.type, params.page_id)


class UpdatePageActionType(UndoableActionType):
    type = "update_page"
    description = ActionTypeDescription(
        _("Update page"),
        _('Page "%(page_name)s" (%(page_id)s) updated'),
        PAGE_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        builder_id: int
        builder_name: str
        page_id: int
        page_name: str
        page_original_params: Dict[str, Any]
        page_new_params: Dict[str, Any]

    @classmethod
    def do(cls, user: AbstractUser, page: Page, **kwargs) -> Page:
        # Captured before the update is applied so it can be reverted.
        original_values, new_values = extract_undo_redo_values(page, kwargs)

        PageService().update_page(user, page, **kwargs)

        builder = page.builder
        cls.register_action(
            user=user,
            params=cls.Params(
                builder.id,
                builder.name,
                page.id,
                page.name,
                original_values,
                new_values,
            ),
            scope=cls.scope(builder.id),
            workspace=builder.workspace,
        )
        return page

    @classmethod
    def scope(cls, builder_id: int) -> ActionScopeStr:
        return ApplicationActionScopeType.value(builder_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        page = PageHandler().get_page(params.page_id)
        PageService().update_page(user, page, **params.page_original_params)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        page = PageHandler().get_page(params.page_id)
        PageService().update_page(user, page, **params.page_new_params)


class DeletePageActionType(UndoableActionType):
    type = "delete_page"
    description = ActionTypeDescription(
        _("Delete page"),
        _('Page "%(page_name)s" (%(page_id)s) deleted'),
        PAGE_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        builder_id: int
        builder_name: str
        page_id: int
        page_name: str

    @classmethod
    def do(cls, user: AbstractUser, page: Page) -> None:
        builder = page.builder
        # Captured before the page is trashed.
        params = cls.Params(builder.id, builder.name, page.id, page.name)

        PageService().delete_page(user, page)

        cls.register_action(
            user=user,
            params=params,
            scope=cls.scope(builder.id),
            workspace=builder.workspace,
        )

    @classmethod
    def scope(cls, builder_id: int) -> ActionScopeStr:
        return ApplicationActionScopeType.value(builder_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        TrashHandler.restore_item(user, PageTrashableItemType.type, params.page_id)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        page = PageHandler().get_page(params.page_id)
        PageService().delete_page(user, page)


class DuplicatePageActionType(UndoableActionType):
    type = "duplicate_page"
    description = ActionTypeDescription(
        _("Duplicate page"),
        _(
            'Page "%(page_name)s" (%(page_id)s) duplicated from '
            '"%(original_page_name)s" (%(original_page_id)s)'
        ),
        PAGE_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        builder_id: int
        builder_name: str
        page_id: int
        page_name: str
        original_page_id: int
        original_page_name: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        page: Page,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Page:
        """
        Duplicates an existing page. Undoing this action trashes the duplicated page
        and redoing restores it.
        """

        page_clone = PageService().duplicate_page(
            user, page, progress_builder=progress_builder
        )

        builder = page.builder
        cls.register_action(
            user=user,
            params=cls.Params(
                builder.id,
                builder.name,
                page_clone.id,
                page_clone.name,
                page.id,
                page.name,
            ),
            scope=cls.scope(builder.id),
            workspace=builder.workspace,
        )
        return page_clone

    @classmethod
    def scope(cls, builder_id: int) -> ActionScopeStr:
        return ApplicationActionScopeType.value(builder_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        page = PageHandler().get_page(params.page_id)
        PageService().delete_page(user, page)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        TrashHandler.restore_item(user, PageTrashableItemType.type, params.page_id)


class OrderPagesActionType(UndoableActionType):
    type = "order_pages"
    description = ActionTypeDescription(
        _("Order pages"),
        _("Pages ordered"),
        PAGE_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        builder_id: int
        builder_name: str
        pages_order: List[int]
        original_pages_order: List[int]

    @classmethod
    def _current_order(cls, builder: Builder) -> List[int]:
        return list(
            Page.objects_without_shared.filter(builder=builder)
            .order_by("order", "id")
            .values_list("id", flat=True)
        )

    @classmethod
    def do(cls, user: AbstractUser, builder: Builder, order: List[int]) -> List[int]:
        original_order = cls._current_order(builder)

        full_order = PageService().order_pages(user, builder, order)

        cls.register_action(
            user=user,
            params=cls.Params(builder.id, builder.name, full_order, original_order),
            scope=cls.scope(builder.id),
            workspace=builder.workspace,
        )
        return full_order

    @classmethod
    def scope(cls, builder_id: int) -> ActionScopeStr:
        return ApplicationActionScopeType.value(builder_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        builder = BuilderHandler().get_builder(params.builder_id)
        PageService().order_pages(user, builder, params.original_pages_order)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        builder = BuilderHandler().get_builder(params.builder_id)
        PageService().order_pages(user, builder, params.pages_order)
