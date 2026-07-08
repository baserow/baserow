from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.contrib.builder.action_scopes import (
    PageActionScopeType,
    SharedPageActionScopeType,
)
from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.data_sources.service import DataSourceService
from baserow.contrib.builder.data_sources.trash_types import (
    DataSourceTrashableItemType,
)
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page
from baserow.core.action.models import Action
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionTypeDescription,
    UndoableActionType,
)
from baserow.core.services.registries import ServiceType, service_type_registry
from baserow.core.trash.handler import TrashHandler

DATA_SOURCE_ACTION_CONTEXT = _(
    'of page (%(page_id)s) in builder "%(builder_name)s" (%(builder_id)s).'
)


def data_source_action_scope(page: Page) -> ActionScopeStr:
    """
    Returns the undo/redo scope for an action on a data source living on ``page``.

    Data sources on the builder's shared page are scoped to that shared page so they
    stay undoable from whichever content page the user is editing. Regular data
    sources are scoped to their own content page.
    """

    if page.shared:
        return SharedPageActionScopeType.value(page.id)
    return PageActionScopeType.value(page.id)


class CreateDataSourceActionType(UndoableActionType):
    type = "create_data_source"
    description = ActionTypeDescription(
        _("Create data source"),
        _("Data source (%(data_source_id)s) created"),
        DATA_SOURCE_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        builder_id: int
        builder_name: str
        page_id: int
        data_source_id: int
        service_type: Optional[str]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        page: Page,
        service_type: Optional[ServiceType] = None,
        before: Optional[DataSource] = None,
        **kwargs,
    ) -> DataSource:
        data_source = DataSourceService().create_data_source(
            user, page, service_type=service_type, before=before, **kwargs
        )

        builder = page.builder
        cls.register_action(
            user=user,
            params=cls.Params(
                builder.id,
                builder.name,
                page.id,
                data_source.id,
                service_type.type if service_type else None,
            ),
            scope=cls.scope(page),
            workspace=builder.workspace,
        )
        return data_source

    @classmethod
    def scope(cls, page: Page):
        return data_source_action_scope(page)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        data_source = DataSourceHandler().get_data_source_for_update(
            params.data_source_id
        )
        DataSourceService().delete_data_source(user, data_source)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        TrashHandler.restore_item(
            user,
            DataSourceTrashableItemType.type,
            params.data_source_id,
        )


class UpdateDataSourceActionType(UndoableActionType):
    type = "update_data_source"
    description = ActionTypeDescription(
        _("Update data source"),
        _("Data source (%(data_source_id)s) updated"),
        DATA_SOURCE_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        builder_id: int
        builder_name: str
        page_id: int
        data_source_id: int
        service_type: Optional[str]
        data_source_original_params: Dict[str, Any]
        data_source_new_params: Dict[str, Any]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        data_source: DataSource,
        service_type: Optional[ServiceType] = None,
        **kwargs,
    ) -> DataSource:
        updated = DataSourceService().update_data_source(
            user, data_source, service_type=service_type, **kwargs
        )

        page = updated.data_source.page
        builder = page.builder
        cls.register_action(
            user=user,
            params=cls.Params(
                builder.id,
                builder.name,
                page.id,
                updated.data_source.id,
                service_type.type if service_type else None,
                updated.original_values,
                updated.new_values,
            ),
            scope=cls.scope(page),
            workspace=builder.workspace,
        )
        return updated.data_source

    @classmethod
    def scope(cls, page: Page):
        return data_source_action_scope(page)

    @classmethod
    def _service_type(cls, params: "UpdateDataSourceActionType.Params"):
        return (
            service_type_registry.get(params.service_type)
            if params.service_type
            else None
        )

    @classmethod
    def _apply(
        cls,
        user: AbstractUser,
        params: "UpdateDataSourceActionType.Params",
        values: Dict[str, Any],
    ):
        data_source = DataSourceHandler().get_data_source_for_update(
            params.data_source_id
        )
        kwargs = dict(values)
        # `page_id` captures a page move (e.g. toggling a data source as shared). The
        # service update expects a `page` instance, so resolve it back here.
        page_id = kwargs.pop("page_id", None)
        if page_id is not None:
            kwargs["page"] = PageHandler().get_page(page_id)
        DataSourceService().update_data_source(
            user,
            data_source,
            service_type=cls._service_type(params),
            **kwargs,
        )

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        cls._apply(user, params, params.data_source_original_params)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        cls._apply(user, params, params.data_source_new_params)


class DeleteDataSourceActionType(UndoableActionType):
    type = "delete_data_source"
    description = ActionTypeDescription(
        _("Delete data source"),
        _("Data source (%(data_source_id)s) deleted"),
        DATA_SOURCE_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        builder_id: int
        builder_name: str
        page_id: int
        data_source_id: int

    @classmethod
    def do(cls, user: AbstractUser, data_source: DataSource) -> None:
        page = data_source.page
        builder = page.builder
        # Captured before the data source is trashed.
        params = cls.Params(
            builder.id,
            builder.name,
            page.id,
            data_source.id,
        )

        DataSourceService().delete_data_source(user, data_source)

        cls.register_action(
            user=user,
            params=params,
            scope=cls.scope(page),
            workspace=builder.workspace,
        )

    @classmethod
    def scope(cls, page: Page):
        return data_source_action_scope(page)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        TrashHandler.restore_item(
            user,
            DataSourceTrashableItemType.type,
            params.data_source_id,
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        data_source = DataSourceHandler().get_data_source_for_update(
            params.data_source_id
        )
        DataSourceService().delete_data_source(user, data_source)


class MoveDataSourceActionType(UndoableActionType):
    type = "move_data_source"
    description = ActionTypeDescription(
        _("Move data source"),
        _("Data source (%(data_source_id)s) moved"),
        DATA_SOURCE_ACTION_CONTEXT,
    )

    @dataclass
    class Params:
        builder_id: int
        builder_name: str
        page_id: int
        data_source_id: int
        original_before_id: Optional[int]
        new_before_id: Optional[int]

    @classmethod
    def _ordered_sibling_ids(cls, data_source: DataSource) -> List[int]:
        return list(
            DataSource.objects.filter(page_id=data_source.page_id)
            .order_by("order", "id")
            .values_list("id", flat=True)
        )

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        data_source: DataSource,
        before: Optional[DataSource] = None,
    ) -> DataSource:
        page = data_source.page
        builder = page.builder

        # Capture the sibling that originally came right after the data source so the
        # move can be undone by placing it back before that sibling.
        sibling_ids = cls._ordered_sibling_ids(data_source)
        index = sibling_ids.index(data_source.id)
        original_before_id = (
            sibling_ids[index + 1] if index + 1 < len(sibling_ids) else None
        )

        moved_data_source = DataSourceService().move_data_source(
            user, data_source, before
        )

        cls.register_action(
            user=user,
            params=cls.Params(
                builder.id,
                builder.name,
                page.id,
                data_source.id,
                original_before_id,
                before.id if before else None,
            ),
            scope=cls.scope(page),
            workspace=builder.workspace,
        )
        return moved_data_source

    @classmethod
    def scope(cls, page: Page):
        return data_source_action_scope(page)

    @classmethod
    def _move(cls, user: AbstractUser, data_source_id: int, before_id: Optional[int]):
        data_source = DataSourceHandler().get_data_source_for_update(data_source_id)
        before = (
            DataSourceHandler().get_data_source(before_id, specific=False)
            if before_id
            else None
        )
        DataSourceService().move_data_source(user, data_source, before)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        cls._move(user, params.data_source_id, params.original_before_id)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        cls._move(user, params.data_source_id, params.new_before_id)
