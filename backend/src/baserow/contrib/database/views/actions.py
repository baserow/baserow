import dataclasses
from collections import defaultdict
from copy import deepcopy
from typing import Any, Dict, List, Optional, Type

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.contrib.database.action.scopes import (
    TABLE_ACTION_CONTEXT,
    VIEW_ACTION_CONTEXT,
    TableActionScopeType,
    ViewActionScopeType,
)
from baserow.contrib.database.fields.exceptions import FieldDoesNotExist
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.rows.exceptions import CannotCreateRowsInTable
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.helpers import (
    construct_entry_from_action_and_diff,
    construct_related_rows_entries,
    extract_row_diff,
    update_related_tables_entries,
)
from baserow.contrib.database.rows.models import RowHistory
from baserow.contrib.database.rows.types import (
    ActionData,
    RelatedRowsDiff,
    RowChangeDiff,
)
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow.contrib.database.views.exceptions import ViewDoesNotExist, ViewNotInTable
from baserow.contrib.database.views.handler import FieldOptionsDict, ViewHandler
from baserow.contrib.database.views.models import (
    FormView,
    View,
    ViewDecoration,
    ViewFilter,
    ViewFilterGroup,
    ViewGroupBy,
    ViewSort,
)
from baserow.core.action.models import Action
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
    UndoableActionType,
)
from baserow.core.action.signals import ActionCommandType
from baserow.core.trash.handler import TrashHandler


class CreateViewFilterActionType(UndoableActionType):
    type = "create_view_filter"
    description = ActionTypeDescription(
        _("Create a view filter"),
        _('View filter created on field "%(field_name)s" (%(field_id)s)'),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "view_id",
        "field_id",
        "table_id",
        "database_id",
        "view_filter_id",
        "filter_type",
        "filter_group_id",
    ]

    @dataclasses.dataclass
    class Params:
        view_id: int
        view_name: str
        field_id: int
        field_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        view_filter_id: int
        filter_type: str
        filter_value: str
        filter_group_id: Optional[int] = None

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        view: View,
        field: Field,
        filter_type: str,
        filter_value: str,
        filter_group_id: Optional[int] = None,
    ) -> ViewFilter:
        """
        Creates a new filter for the provided view.
        See baserow.contrib.database.views.handler.ViewHandler.create_filter
        for more. When undone the view_filter is fully deleted from the
        database and when redone it is recreated with the same id.

        :param user: The user creating the filter.
        :param view: The view to create the filter for.
        :param field: The field to filter by.
        :param filter_type: Indicates how the field's value
        must be compared to the filter's value.
        :param filter_value: The filter value that must be
        compared to the field's value.
        :param filter_group_id: The id of the filter group to add the filter to.
        """

        view_filter = ViewHandler().create_filter(
            user, view, field, filter_type, filter_value, filter_group_id
        )

        workspace = view.table.database.workspace
        params = cls.Params(
            view.id,
            view.name,
            field.id,
            field.name,
            view.table.id,
            view.table.name,
            view.table.database.id,
            view.table.database.name,
            view_filter.id,
            filter_type,
            filter_value,
            filter_group_id,
        )
        cls.register_action(user, params, cls.scope(view.id), workspace)
        return view_filter

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        view_filter = ViewHandler().get_filter(user, params.view_filter_id)

        ViewHandler().delete_filter(user, view_filter)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        view_handler = ViewHandler()
        view = view_handler.get_view(params.view_id)
        field = FieldHandler().get_field(params.field_id)

        view_handler.create_filter(
            user,
            view,
            field,
            params.filter_type,
            params.filter_value,
            params.filter_group_id,
            primary_key=params.view_filter_id,
        )


# TODO: What to do here with fast UI updates?
# Every time a user type a character in the filter input, a new action is created.
# This means every single change ends in the undo/redo stack and in the audit log.
class UpdateViewFilterActionType(UndoableActionType):
    type = "update_view_filter"
    description = ActionTypeDescription(
        _("Update a view filter"),
        _('View filter updated on field "%(field_name)s" (%(field_id)s)'),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "field_id",
        "view_id",
        "table_id",
        "database_id",
        "view_filter_id",
        "filter_type",
        "original_field_id",
        "original_filter_type",
    ]

    @dataclasses.dataclass
    class Params:
        field_id: int
        field_name: str
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        view_filter_id: int
        filter_type: str
        filter_value: str
        original_field_id: int
        original_field_name: str
        original_filter_type: str
        original_filter_value: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        view_filter: ViewFilter,
        field: Optional[Field] = None,
        filter_type: Optional[str] = None,
        filter_value: Optional[str] = None,
    ) -> ViewFilter:
        """
        Updates the values of an existing view filter.
        See baserow.contrib.database.views.handler.ViewHandler.update_filter
        for more. When undone the view_filter is restored to it's original state
        and when redone it is updated to it's new state.

        :param user: The user on whose behalf the view filter is updated.
        :param view_filter: The view filter that needs to be updated.
        :param field: The model of the field to filter by.
        :param filter_type: Indicates how the field's value
        must be compared to the filter's value.
        :param filter_value: The filter value that must be
        compared to the field's value.
        """

        original_view_filter_field_id = view_filter.field_id
        original_view_filter_field_name = view_filter.field.name
        original_view_filter_type = view_filter.type
        original_view_filter_value = view_filter.value

        view_handler = ViewHandler()
        updated_view_filter = view_handler.update_filter(
            user, view_filter, field, filter_type, filter_value
        )
        view = view_filter.view
        params = cls.Params(
            updated_view_filter.field.id,
            updated_view_filter.field.name,
            view.id,
            view.name,
            view.table.id,
            view.table.name,
            view.table.database.id,
            view.table.database.name,
            view_filter.id,
            updated_view_filter.type,
            updated_view_filter.value,
            original_view_filter_field_id,
            original_view_filter_field_name,
            original_view_filter_type,
            original_view_filter_value,
        )
        workspace = updated_view_filter.field.table.database.workspace
        cls.register_action(
            user,
            params,
            cls.scope(view_filter.view_id),
            workspace,
        )

        return updated_view_filter

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        field = FieldHandler().get_field(params.original_field_id)

        view_handler = ViewHandler()
        view_filter = view_handler.get_filter(user, params.view_filter_id)

        view_handler.update_filter(
            user,
            view_filter,
            field,
            params.original_filter_type,
            params.original_filter_value,
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        field = FieldHandler().get_field(params.field_id)

        view_handler = ViewHandler()
        view_filter = view_handler.get_filter(user, params.view_filter_id)

        view_handler.update_filter(
            user,
            view_filter,
            field,
            params.filter_type,
            params.filter_value,
        )


class DeleteViewFilterActionType(UndoableActionType):
    type = "delete_view_filter"
    description = ActionTypeDescription(
        _("Delete a view filter"),
        _('View filter deleted from field "%(field_name)s" (%(field_id)s)'),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "field_id",
        "view_id",
        "table_id",
        "database_id",
        "view_filter_id",
        "filter_type",
        "filter_group_id",
    ]

    @dataclasses.dataclass
    class Params:
        field_id: int
        field_name: str
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        view_filter_id: int
        filter_type: str
        filter_value: str
        filter_group_id: Optional[int] = None

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        view_filter: ViewFilter,
    ):
        """
        Deletes an existing view filter.
        See baserow.contrib.database.views.handler.ViewHandler.delete_filter
        for more. When undone the view_filter is recreated and when redone
        it is deleted.

        :param user: The user on whose behalf the view filter is deleted.
        :param view_filter: The view filter that needs to be deleted.
        """

        view_filter_id = view_filter.id
        view_id = view_filter.view_id
        view_name = view_filter.view.name
        field_id = view_filter.field_id
        field_name = view_filter.field.name
        view_filter_type = view_filter.type
        view_filter_value = view_filter.value
        view_filter_group_id = view_filter.group_id

        ViewHandler().delete_filter(user, view_filter)

        params = cls.Params(
            field_id,
            field_name,
            view_id,
            view_name,
            view_filter.view.table.id,
            view_filter.view.table.name,
            view_filter.view.table.database.id,
            view_filter.view.table.database.name,
            view_filter_id,
            view_filter_type,
            view_filter_value,
            view_filter_group_id,
        )
        workspace = view_filter.view.table.database.workspace
        cls.register_action(
            user,
            params,
            cls.scope(
                view_filter.view_id,
            ),
            workspace,
        )

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        view_handler = ViewHandler()
        view = view_handler.get_view(params.view_id)
        field = FieldHandler().get_field(params.field_id)

        view_handler.create_filter(
            user,
            view,
            field,
            params.filter_type,
            params.filter_value,
            params.filter_group_id,
            params.view_filter_id,
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        view_filter = ViewHandler().get_filter(user, params.view_filter_id)

        ViewHandler().delete_filter(user, view_filter)


class CreateViewFilterGroupActionType(UndoableActionType):
    type = "create_view_filter_group"
    description = ActionTypeDescription(
        _("Create a view filter group"),
        _("View filter group created"),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "view_id",
        "table_id",
        "database_id",
        "view_filter_group_id",
        "filter_type",
        "parent_group_id",
    ]

    @dataclasses.dataclass
    class Params:
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        view_filter_group_id: int
        filter_type: str
        parent_group_id: Optional[int] = None

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        view: View,
        filter_type: Optional[str] = None,
        parent_group: Optional[int] = None,
    ) -> ViewFilterGroup:
        """
        Creates a new filter group for the provided view. See
        baserow.contrib.database.views.handler.ViewHandler.create_filter_group
        for more. When undone the view_filter_group is fully deleted from the
        database and when redone it is recreated with the same id.

        :param user: The user creating the filter.
        :param view: The view to create the filter for.
        :param field: The field to filter by.
        :param filter_type: Indicates whether all the rows should apply to all
            filters (AND) or to any filter (OR) in the group to be shown.
        """

        view_filter_group = ViewHandler().create_filter_group(
            user, view, filter_type, parent_group
        )

        workspace = view.table.database.workspace
        params = cls.Params(
            view.id,
            view.name,
            view.table.id,
            view.table.name,
            view.table.database.id,
            view.table.database.name,
            view_filter_group.id,
            filter_type,
            parent_group,
        )
        cls.register_action(user, params, cls.scope(view.id), workspace)
        return view_filter_group

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        view_filter_group = ViewHandler().get_filter_group(
            user, params.view_filter_group_id
        )

        ViewHandler().delete_filter_group(user, view_filter_group)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        view_handler = ViewHandler()
        view = view_handler.get_view(params.view_id)

        view_handler.create_filter_group(
            user,
            view,
            params.filter_type,
            params.parent_group_id,
            params.view_filter_group_id,
        )


class UpdateViewFilterGroupActionType(UndoableActionType):
    type = "update_view_filter_group"
    description = ActionTypeDescription(
        _("Update a view filter group"),
        _('View filter group updated to "%(filter_type)s"'),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "view_id",
        "table_id",
        "database_id",
        "view_filter_group_id",
        "filter_type",
        "original_filter_type",
    ]

    @dataclasses.dataclass
    class Params:
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        view_filter_group_id: int
        filter_type: str
        original_filter_type: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        view_filter_group: ViewFilterGroup,
        filter_type: Optional[str] = None,
    ) -> ViewFilterGroup:
        """
        Updates the filter_type of an existing filter group. See
        baserow.contrib.database.views.handler.ViewHandler.update_filter_group
        for more. When undone the view_filter_group is restored to it's original
        filter_type and when redone it is updated to the new one.

        :param user: The user on whose behalf the view filter is updated.
        :param view_filter_group: The view filter group that needs to be
            updated.
        :param filter_type: ndicates whether all the rows should apply to all
            filters (AND) or to any filter (OR) in the group to be shown.
        """

        original_view_filter_type = view_filter_group.filter_type

        view_handler = ViewHandler()
        updated_view_filter_group = view_handler.update_filter_group(
            user, view_filter_group, filter_type
        )
        view = view_filter_group.view
        params = cls.Params(
            view.id,
            view.name,
            view.table.id,
            view.table.name,
            view.table.database.id,
            view.table.database.name,
            view_filter_group.id,
            updated_view_filter_group.filter_type,
            original_view_filter_type,
        )
        workspace = updated_view_filter_group.view.table.database.workspace
        cls.register_action(
            user,
            params,
            cls.scope(view_filter_group.view_id),
            workspace,
        )

        return updated_view_filter_group

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        view_handler = ViewHandler()
        view_filter_group = view_handler.get_filter_group(
            user, params.view_filter_group_id
        )

        view_handler.update_filter_group(
            user, view_filter_group, params.original_filter_type
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        view_handler = ViewHandler()
        view_filter_group = view_handler.get_filter_group(
            user, params.view_filter_group_id
        )

        view_handler.update_filter_group(user, view_filter_group, params.filter_type)


class DeleteViewFilterGroupActionType(UndoableActionType):
    type = "delete_view_filter_group"
    description = ActionTypeDescription(
        _("Delete a view filter group"),
        _("View filter group deleted"),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "view_id",
        "table_id",
        "database_id",
        "view_filter_group_id",
        "filter_type",
    ]

    @dataclasses.dataclass
    class Params:
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        view_filter_group_id: int
        filter_type: str
        filters: List[Dict[str, Any]]
        parent_group_id: Optional[int] = None
        groups: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        view_filter_group: ViewFilterGroup,
    ):
        """
        Deletes an existing view filter group with all the filters. See
        baserow.contrib.database.views.handler.ViewHandler.delete_filter_group
        for more. When undone the view_filter_group is recreated with all the
        filters and when redone it is deleted again.

        :param user: The user on whose behalf the view filter is deleted.
        :param view_filter_group: The view filter group that needs to be
            deleted.
        """

        view_filter_group_id = view_filter_group.id
        view_id = view_filter_group.view_id
        view_name = view_filter_group.view.name
        view_filter_type = view_filter_group.filter_type

        filters = []
        groups = []

        def append_filters(filter_group):
            for view_filter in filter_group.filters.all():
                filters.append(
                    {
                        "id": view_filter.id,
                        "field_id": view_filter.field_id,
                        "filter_type": view_filter.type,
                        "filter_value": view_filter.value,
                        "group_id": view_filter.group_id,
                    }
                )

        def append_filter_groups(filter_group):
            append_filters(filter_group)
            for child_filter_group in filter_group.viewfiltergroup_set.all():
                groups.append(
                    {
                        "id": child_filter_group.id,
                        "filter_type": child_filter_group.filter_type,
                        "parent_group_id": child_filter_group.parent_group_id,
                    }
                )
                append_filter_groups(child_filter_group)

        append_filter_groups(view_filter_group)

        ViewHandler().delete_filter_group(user, view_filter_group)

        params = cls.Params(
            view_id,
            view_name,
            view_filter_group.view.table.id,
            view_filter_group.view.table.name,
            view_filter_group.view.table.database.id,
            view_filter_group.view.table.database.name,
            view_filter_group_id,
            view_filter_type,
            filters,
            view_filter_group.parent_group_id,
            groups,
        )
        workspace = view_filter_group.view.table.database.workspace
        cls.register_action(
            user,
            params,
            cls.scope(view_filter_group.view_id),
            workspace,
        )

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        view_handler = ViewHandler()
        view = view_handler.get_view(params.view_id)

        view_handler.create_filter_group(
            user,
            view,
            params.filter_type,
            params.parent_group_id,
            params.view_filter_group_id,
        )

        inner_groups = params.groups or []
        for filter_group in inner_groups:
            view_handler.create_filter_group(
                user,
                view,
                filter_group["filter_type"],
                filter_group["parent_group_id"],
                filter_group["id"],
            )

        # recreate all the filters belonging to the group
        for view_filter in params.filters:
            try:
                field = FieldHandler().get_field(view_filter["field_id"])
            except FieldDoesNotExist:
                continue
            view_handler.create_filter(
                user,
                view,
                field,
                view_filter["filter_type"],
                view_filter["filter_value"],
                view_filter["group_id"],
                primary_key=view_filter["id"],
            )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        view_filter_group = ViewHandler().get_filter_group(
            user, params.view_filter_group_id
        )

        ViewHandler().delete_filter_group(user, view_filter_group)


class CreateViewSortActionType(UndoableActionType):
    type = "create_view_sort"
    description = ActionTypeDescription(
        _("Create a view sort"),
        _('View sorted on field "%(field_name)s" (%(field_id)s)'),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "field_id",
        "view_id",
        "table_id",
        "database_id",
        "view_sort_id",
        "sort_order",
        "sort_type",
    ]

    @dataclasses.dataclass
    class Params:
        field_id: int
        field_name: str
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        view_sort_id: int
        sort_order: str
        sort_type: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        view: View,
        field: Field,
        sort_order: str,
        sort_type: Optional[str] = None,
    ) -> ViewSort:
        """
        Creates a new view sort.
        See baserow.contrib.database.views.handler.ViewHandler.create_sort
        for more. When undone the view_sort is fully deleted from the
        database and when redone it is recreated.

        :param user: The user on whose behalf the view sort is created.
        :param view: The view for which the sort needs to be created.
        :param field: The field that needs to be sorted.
        :param sort_order: The desired order, can either be ascending (A to Z) or
            descending (Z to A).
        :param sort_type: The sort type that must be used, `default` is set as default
            when the sort is created.
        """

        view_sort = ViewHandler().create_sort(
            user, view, field, sort_order, sort_type=sort_type
        )

        params = cls.Params(
            field.id,
            field.name,
            view.id,
            view.name,
            view.table.id,
            view.table.name,
            view.table.database.id,
            view.table.database.name,
            view_sort.id,
            sort_order,
            sort_type,
        )
        workspace = view.table.database.workspace
        cls.register_action(user, params, cls.scope(view.id), workspace)
        return view_sort

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        view_sort = ViewHandler().get_sort(user, params.view_sort_id)

        ViewHandler().delete_sort(user, view_sort)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        view_handler = ViewHandler()
        field = FieldHandler().get_field(params.field_id)
        view = view_handler.get_view(params.view_id)

        view_handler.create_sort(
            user,
            view,
            field,
            params.sort_order,
            params.view_sort_id,
            params.sort_type,
        )


class UpdateViewSortActionType(UndoableActionType):
    type = "update_view_sort"
    description = ActionTypeDescription(
        _("Update a view sort"),
        _('View sort updated on field "%(field_name)s" (%(field_id)s)'),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "field_id",
        "view_id",
        "table_id",
        "database_id",
        "view_sort_id",
        "sort_order",
        "sort_type",
        "original_field_id",
        "original_sort_order",
        "original_sort_type",
    ]

    @dataclasses.dataclass
    class Params:
        field_id: int
        field_name: str
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        view_sort_id: int
        sort_order: str
        sort_type: str
        original_field_id: int
        original_field_name: str
        original_sort_order: str
        original_sort_type: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        view_sort: ViewSort,
        field: Optional[Field] = None,
        order: Optional[str] = None,
        sort_type: Optional[str] = None,
    ) -> ViewSort:
        """
        Updates the values of an existing view sort.
        See baserow.contrib.database.views.handler.ViewHandler.update_sort
        for more. When undone the view_sort is restored to it's original state
        and when redone it is updated to it's new state.

        :param user: The user on whose behalf the view sort is updated.
        :param view_sort: The view sort that needs to be updated.
        :param field: The field that must be sorted on.
        :param order: Indicates the sort order direction.
        :param sort_type: The sort type that must be used, `default` is set as default
            when the sort is created.
        """

        original_field_id = view_sort.field.id
        original_field_name = view_sort.field.name
        view_id = view_sort.view.id
        view_name = view_sort.view.name
        original_sort_order = view_sort.order
        original_sort_type = view_sort.type

        handler = ViewHandler()
        updated_view_sort = handler.update_sort(
            user, view_sort, field, order, sort_type
        )

        cls.register_action(
            user=user,
            params=cls.Params(
                updated_view_sort.field.id,
                updated_view_sort.field.name,
                view_id,
                view_name,
                updated_view_sort.view.table.id,
                updated_view_sort.view.table.name,
                updated_view_sort.view.table.database.id,
                updated_view_sort.view.table.database.name,
                updated_view_sort.id,
                updated_view_sort.order,
                updated_view_sort.type,
                original_field_id,
                original_field_name,
                original_sort_order,
                original_sort_type,
            ),
            scope=cls.scope(view_sort.view.id),
            workspace=view_sort.view.table.database.workspace,
        )

        return updated_view_sort

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        field = FieldHandler().get_field(params.original_field_id)

        view_handler = ViewHandler()
        view_sort = view_handler.get_sort(user, params.view_sort_id)

        view_handler.update_sort(
            user,
            view_sort,
            field,
            params.original_sort_order,
            params.original_sort_type,
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        field = FieldHandler().get_field(params.field_id)

        view_handler = ViewHandler()
        view_sort = view_handler.get_sort(user, params.view_sort_id)

        view_handler.update_sort(
            user, view_sort, field, params.sort_order, params.sort_type
        )


class DeleteViewSortActionType(UndoableActionType):
    type = "delete_view_sort"
    description = ActionTypeDescription(
        _("Delete a view sort"),
        _('View sort deleted from field "%(field_name)s" (%(field_id)s)'),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "field_id",
        "view_id",
        "table_id",
        "database_id",
        "view_sort_id",
        "sort_order",
        "sort_type",
    ]

    @dataclasses.dataclass
    class Params:
        field_id: int
        field_name: str
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        view_sort_id: int
        sort_order: str
        sort_type: str

    @classmethod
    def do(cls, user: AbstractUser, view_sort: ViewSort):
        """
        Deletes an existing view sort.
        See baserow.contrib.database.views.handler.ViewHandler.delete_sort
        for more. When undone the view_sort is recreated and when redone
        it is deleted.

        :param user: The user on whose behalf the view sort is deleted.
        :param view_sort: The view sort instance that needs
        to be deleted.
        """

        view_sort_id = view_sort.id
        view_id = view_sort.view.id
        view_name = view_sort.view.name
        field_id = view_sort.field.id
        field_name = view_sort.field.name
        sort_order = view_sort.order
        sort_type = view_sort.type

        ViewHandler().delete_sort(user, view_sort)

        params = cls.Params(
            field_id,
            field_name,
            view_id,
            view_name,
            view_sort.view.table.id,
            view_sort.view.table.name,
            view_sort.view.table.database.id,
            view_sort.view.table.database.name,
            view_sort_id,
            sort_order,
            sort_type,
        )
        workspace = view_sort.view.table.database.workspace
        cls.register_action(user, params, cls.scope(view_sort.view.id), workspace)

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        view_handler = ViewHandler()
        view = view_handler.get_view(params.view_id)
        field = FieldHandler().get_field(params.field_id)

        view_handler.create_sort(
            user,
            view,
            field,
            params.sort_order,
            params.view_sort_id,
            params.sort_type,
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        view_sort = ViewHandler().get_sort(user, params.view_sort_id)
        ViewHandler().delete_sort(user, view_sort)


class OrderViewsActionType(UndoableActionType):
    type = "order_views"
    description = ActionTypeDescription(
        _("Order views"), _("Views order changed"), TABLE_ACTION_CONTEXT
    )
    analytics_params = [
        "table_id",
        "database_id",
    ]

    @dataclasses.dataclass
    class Params:
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        order: List[int]
        original_order: List[int]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        table: Table,
        order: List[int],
    ):
        """
        Updates the order of the views in the given table.
        See baserow.contrib.views.handler.ViewsHandler.order_views for further details.
        The order of the views that are not in the `order` parameter set to `0`.
        Undoing this action restores the original order of the views.
        Redoing this action reorders the views to the new order.

        :param user: The user ordering the views.
        :param table: The table to order the views in.
        :param order: The new order of the views.
        """

        try:
            view = ViewHandler().get_view(order[0])
        except ViewDoesNotExist:
            raise ViewNotInTable
        original_order = ViewHandler().get_views_order(user, table, view.ownership_type)

        ViewHandler().order_views(user, table, order)

        params = cls.Params(
            table.id,
            table.name,
            table.database.id,
            table.database.name,
            order,
            original_order,
        )
        cls.register_action(user, params, cls.scope(table.id), table.database.workspace)

    @classmethod
    def scope(cls, table_id: int) -> ActionScopeStr:
        return TableActionScopeType.value(table_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        table = TableHandler().get_table(params.table_id)
        ViewHandler().order_views(user, table, params.original_order)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        table = TableHandler().get_table(params.table_id)
        ViewHandler().order_views(user, table, params.order)


class UpdateViewFieldOptionsActionType(UndoableActionType):
    type = "update_view_field_options"
    description = ActionTypeDescription(
        _("Update view field options"),
        _("ViewFieldOptions updated"),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "view_id",
        "table_id",
        "database_id",
        "field_options",
        "original_field_options",
    ]

    @dataclasses.dataclass
    class Params:
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        field_options: FieldOptionsDict
        original_field_options: FieldOptionsDict

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        view: View,
        field_options: FieldOptionsDict,
    ):
        """
        Updates the field options for the current view.
        See baserow.contrib.database.views.handler.ViewHandler.update_field_options
        for more.
        Undoing this action restores the original field options.
        Redoing this action updates the field options to the new ones.

        :param user: The user creating the filter.
        :param view: The view of the field_optinos to update.
        :param field_options: The field options to set.
        """

        original_field_options = {
            fo["field_id"]: fo
            for fo in view.get_field_options(create_if_missing=True).values()
        }

        ViewHandler().update_field_options(
            user=user, view=view, field_options=field_options
        )

        # save only field_options that have changed from the original value
        new_field_options_to_save = defaultdict(dict)
        original_field_options_to_save = defaultdict(dict)

        for field_id, new_options in field_options.items():
            original_options = original_field_options.get(field_id, {})
            for key, new_value in new_options.items():
                original_value = original_options.get(key, None)
                if new_value != original_value:
                    original_field_options_to_save[field_id][key] = original_value
                    new_field_options_to_save[field_id][key] = new_value

        cls.register_action(
            user=user,
            params=cls.Params(
                view.id,
                view.name,
                view.table.id,
                view.table.name,
                view.table.database.id,
                view.table.database.name,
                dict(new_field_options_to_save),
                dict(original_field_options_to_save),
            ),
            scope=cls.scope(view.id),
            workspace=view.table.database.workspace,
        )

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        view_handler = ViewHandler()
        view = view_handler.get_view(params.view_id).specific
        view_handler.update_field_options(
            user=user, view=view, field_options=params.original_field_options
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        view_handler = ViewHandler()
        view = view_handler.get_view(params.view_id).specific
        view_handler.update_field_options(
            user=user, view=view, field_options=params.field_options
        )


class RotateViewSlugActionType(UndoableActionType):
    type = "rotate_view_slug"
    description = ActionTypeDescription(
        _("View slug URL updated"),
        _("View changed public slug URL"),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "view_id",
        "table_id",
        "database_id",
    ]

    @dataclasses.dataclass
    class Params:
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        slug: str
        original_slug: str

    @classmethod
    def do(cls, user: AbstractUser, view: View) -> View:
        """
        Change the slug for the current view.
        See baserow.contrib.database.views.handler.ViewHandler.rotate_slug for more.
        Undoing this action restores the original slug.
        Redoing this action updates the slug to the new one.

        :param user: The user creating the filter.
        :param view: The view of the slug to update.
        """

        original_slug = view.slug

        ViewHandler().rotate_view_slug(user, view)

        cls.register_action(
            user=user,
            params=cls.Params(
                view.id,
                view.name,
                view.table.id,
                view.table.name,
                view.table.database.id,
                view.table.database.name,
                view.slug,
                original_slug,
            ),
            scope=cls.scope(view.id),
            workspace=view.table.database.workspace,
        )
        return view

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        view_handler = ViewHandler()
        view = view_handler.get_view_for_update(user, params.view_id)
        view_handler.update_view_slug(user, view, params.original_slug)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        view_handler = ViewHandler()
        view = view_handler.get_view_for_update(user, params.view_id)
        view_handler.update_view_slug(user, view, params.slug)


class UpdateViewActionType(UndoableActionType):
    type = "update_view"
    description = ActionTypeDescription(
        _("Update view"),
        _('View "%(view_name)s" (%(view_id)s) updated'),
        TABLE_ACTION_CONTEXT,
    )
    analytics_params = [
        "view_id",
        "view_ownership_type",
        "table_id",
        "database_id",
    ]

    @dataclasses.dataclass
    class Params:
        view_id: int
        view_name: str
        view_ownership_type: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        data: Dict[str, Any]
        original_data: Dict[str, Any]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        view: View,
        **data,
    ) -> View:
        """
        Updates the current view.
        See baserow.contrib.database.views.handler.ViewHandler.update_view for more.
        Undoing this action restores the original values.
        Redoing this action updates the values to the new ones.

        :param user: The user creating the filter.
        :param view: The view of the slug to update.
        :params data: The data to update.
        """

        updated_view_with_changes = ViewHandler().update_view(user, view, **data)
        view = updated_view_with_changes.updated_view_instance

        cls.register_action(
            user=user,
            params=cls.Params(
                view.id,
                view.name,
                view.ownership_type,
                view.table.id,
                view.table.name,
                view.table.database.id,
                view.table.database.name,
                updated_view_with_changes.new_view_attributes,
                updated_view_with_changes.original_view_attributes,
            ),
            scope=cls.scope(view.id),
            workspace=view.table.database.workspace,
        )
        return view

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        view_handler = ViewHandler()
        view = view_handler.get_view_for_update(user, params.view_id).specific
        view_handler.update_view(user, view, **params.original_data)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        view_handler = ViewHandler()
        view = view_handler.get_view_for_update(user, params.view_id).specific
        view_handler.update_view(user, view, **params.data)


class CreateViewActionType(UndoableActionType):
    type = "create_view"
    description = ActionTypeDescription(
        _("Create view"),
        _('View "%(view_name)s" (%(view_id)s) created'),
        TABLE_ACTION_CONTEXT,
    )
    analytics_params = [
        "view_id",
        "view_type",
        "table_id",
        "database_id",
    ]

    @dataclasses.dataclass
    class Params:
        view_id: int
        view_name: str
        view_type: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str

    @classmethod
    def do(cls, user: AbstractUser, table: Table, type_name: str, **kwargs) -> View:
        """
        Creates a new view based on the provided type.
        See baserow.contrib.views.handler.ViewsHandler.create_view for further details.
        Undoing this action deletes the view.
        Redoing this action restores the view.

        :param user: The user creating the view.
        :param table: The table to create the view in.
        :param type_name: The type of the view.
        :param kwargs: The parameters of the view.
        """

        view = ViewHandler().create_view(
            user,
            table,
            type_name,
            **kwargs,
        )

        cls.register_action(
            user=user,
            params=cls.Params(
                view.id,
                view.name,
                type_name,
                table.id,
                table.name,
                table.database.id,
                table.database.name,
            ),
            scope=cls.scope(table.id),
            workspace=table.database.workspace,
        )

        return view

    @classmethod
    def scope(cls, table_id: int) -> ActionScopeStr:
        return TableActionScopeType.value(table_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        ViewHandler().delete_view_by_id(user, params.view_id)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        TrashHandler.restore_item(user, "view", params.view_id)


class DuplicateViewActionType(UndoableActionType):
    type = "duplicate_view"
    description = ActionTypeDescription(
        _("Duplicate view"),
        _(
            'View "%(view_name)s" (%(view_id)s) duplicated from '
            'view "%(original_view_name)s" (%(original_view_id)s)'
        ),
        TABLE_ACTION_CONTEXT,
    )
    analytics_params = [
        "view_id",
        "table_id",
        "database_id",
        "original_view_id",
    ]

    @dataclasses.dataclass
    class Params:
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        original_view_id: int
        original_view_name: str

    @classmethod
    def do(cls, user: AbstractUser, original_view: View) -> View:
        """
        Duplicate an existing view.

        Undoing this action deletes the new view.
        Redoing this action restores the view.

        :param user: The user creating the view.
        :param original_view: The view to duplicate.
        """

        view = ViewHandler().duplicate_view(
            user,
            original_view,
        )

        cls.register_action(
            user=user,
            params=cls.Params(
                view.id,
                view.name,
                original_view.table.id,
                original_view.table.name,
                original_view.table.database.id,
                original_view.table.database.name,
                original_view.id,
                original_view.name,
            ),
            scope=cls.scope(original_view.table.id),
            workspace=original_view.table.database.workspace,
        )

        return view

    @classmethod
    def scope(cls, table_id: int) -> ActionScopeStr:
        return TableActionScopeType.value(table_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        ViewHandler().delete_view_by_id(user, params.view_id)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        TrashHandler.restore_item(user, "view", params.view_id)


class DeleteViewActionType(UndoableActionType):
    type = "delete_view"
    description = ActionTypeDescription(
        _("Delete view"),
        _('View "%(view_name)s" (%(view_id)s) deleted'),
        TABLE_ACTION_CONTEXT,
    )
    analytics_params = [
        "view_id",
        "table_id",
        "database_id",
    ]

    @dataclasses.dataclass
    class Params:
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str

    @classmethod
    def do(cls, user: AbstractUser, view: View):
        """
        Trashes an existing view instance.
        See baserow.contrib.views.handler.ViewsHandler.delete_view for further details.
        Undoing this action restores the view.
        Redoing this action deletes the view again.

        :param user: The user deleting the view.
        :param view: The view to delete.
        """

        ViewHandler().delete_view(user, view)

        cls.register_action(
            user=user,
            params=cls.Params(
                view.id,
                view.name,
                view.table.id,
                view.table.name,
                view.table.database.id,
                view.table.database.name,
            ),
            scope=cls.scope(view.table_id),
            workspace=view.table.database.workspace,
        )

    @classmethod
    def scope(cls, table_id: int) -> ActionScopeStr:
        return TableActionScopeType.value(table_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        TrashHandler.restore_item(user, "view", params.view_id)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        ViewHandler().delete_view_by_id(user, params.view_id)


class CreateDecorationActionType(UndoableActionType):
    type = "create_decoration"
    description = ActionTypeDescription(
        _("Create decoration"),
        _("View decoration %(decorator_id)s created"),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "view_id",
        "table_id",
        "database_id",
        "decorator_id",
        "decorator_type_name",
        "value_provider_type_name",
        "value_provider_conf",
    ]

    @dataclasses.dataclass
    class Params:
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        decorator_id: int
        decorator_type_name: str
        value_provider_type_name: str
        value_provider_conf: Dict[str, Any]

    @classmethod
    def do(
        cls,
        view: View,
        decorator_type_name: str,
        value_provider_type_name: str,
        value_provider_conf: Dict[str, Any],
        user: AbstractUser,
    ) -> ViewDecoration:
        """
        Creates a new decoration based on the provided type.
        See baserow.contrib.decorations.handler.DecorationsHandler.create_decoration
        for further details.
        Undoing this action deletes the decoration.

        :param view: The view for which the filter needs to be created.
        :param decorator_type_name: The type of the decorator.
        :param value_provider_type_name: The value provider that provides the value
            to the decorator.
        :param value_provider_conf: The configuration used by the value provider to
            compute the values for the decorator.
        :param user: Optional user who have created the decoration.
        :return: The created view decoration instance.
        """

        decoration = ViewHandler().create_decoration(
            view,
            decorator_type_name,
            value_provider_type_name,
            value_provider_conf,
            user=user,
        )

        cls.register_action(
            user=user,
            params=cls.Params(
                view.id,
                view.name,
                view.table.id,
                view.table.name,
                view.table.database.id,
                view.table.database.name,
                decoration.id,
                decorator_type_name,
                value_provider_type_name,
                value_provider_conf,
            ),
            scope=cls.scope(view.id),
            workspace=view.table.database.workspace,
        )

        return decoration

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        view_decoration = ViewHandler().get_decoration(user, params.decorator_id)
        ViewHandler().delete_decoration(view_decoration, user=user)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        view = ViewHandler().get_view(params.view_id)
        ViewHandler().create_decoration(
            view,
            params.decorator_type_name,
            params.value_provider_type_name,
            params.value_provider_conf,
            user=user,
            primary_key=params.decorator_id,
        )


class UpdateDecorationActionType(UndoableActionType):
    type = "update_decoration"
    description = ActionTypeDescription(
        _("Update decoration"),
        _("View decoration %(decorator_id)s updated"),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "view_id",
        "table_id",
        "database_id",
        "decorator_id",
        "original_decoration_type_name",
        "original_value_provider_type_name",
        "original_value_provider_conf",
        "original_order",
        "new_decorator_type_name" "new_value_provider_type_name",
        "new_value_provider_conf",
        "new_order",
    ]

    @dataclasses.dataclass
    class Params:
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        decorator_id: int
        original_decoration_type_name: str
        original_value_provider_type_name: str
        original_value_provider_conf: Dict[str, Any]
        original_order: int
        new_decorator_type_name: str
        new_value_provider_type_name: str
        new_value_provider_conf: Dict[str, Any]
        new_order: int

    @classmethod
    def do(
        cls,
        view_decoration: ViewDecoration,
        user: AbstractUser,
        decorator_type_name: str = None,
        value_provider_type_name: str = None,
        value_provider_conf: Dict[str, Any] = None,
        order: int = None,
    ) -> ViewDecoration:
        """
        Updates the values of an existing view decoration.
        See baserow.contrib.decorations.handler.DecorationsHandler.update_decoration
        for further details.
        Undoing this action will revert the changes.
        Redoing this action will apply the changes again.

        :param view_decoration: The view decoration that needs to be updated.
        :param user: Optional user who have created the decoration..
        :param decorator_type_name: The type of the decorator.
        :param value_provider_type_name: The value provider that provides the value
            to the decorator.
        :param value_provider_conf: The configuration used by the value provider to
            compute the values for the decorator.
        :param order: The order of the decoration.
        :param user: Optional user who have updated the decoration.
        :return: The updated view decoration instance.
        """

        original_view_decoration = deepcopy(view_decoration)
        original_decoration_type_name = original_view_decoration.type
        original_value_provider_type_name = original_view_decoration.value_provider_type
        original_value_provider_conf = original_view_decoration.value_provider_conf
        original_order = original_view_decoration.order
        view = view_decoration.view

        view_decoration_updated = ViewHandler().update_decoration(
            view_decoration,
            user=user,
            decorator_type_name=decorator_type_name,
            value_provider_type_name=value_provider_type_name,
            value_provider_conf=value_provider_conf,
            order=order,
        )

        cls.register_action(
            user=user,
            params=cls.Params(
                view.id,
                view.name,
                view.table.id,
                view.table.name,
                view.table.database.id,
                view.table.database.name,
                view_decoration.id,
                original_decoration_type_name,
                original_value_provider_type_name,
                original_value_provider_conf,
                original_order,
                decorator_type_name,
                value_provider_type_name,
                value_provider_conf,
                order,
            ),
            scope=cls.scope(view_decoration.view_id),
            workspace=view.table.database.workspace,
        )

        return view_decoration_updated

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_being_undone: Action):
        view_decoration = ViewHandler().get_decoration(user, params.decorator_id)
        ViewHandler().update_decoration(
            view_decoration,
            user=user,
            decorator_type_name=params.original_decoration_type_name,
            value_provider_type_name=params.original_value_provider_type_name,
            value_provider_conf=params.original_value_provider_conf,
            order=params.original_order,
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        view_decoration = ViewHandler().get_decoration(user, params.decorator_id)
        ViewHandler().update_decoration(
            view_decoration,
            user=user,
            decorator_type_name=params.new_decorator_type_name,
            value_provider_type_name=params.new_value_provider_type_name,
            value_provider_conf=params.new_value_provider_conf,
            order=params.new_order,
        )


class DeleteDecorationActionType(UndoableActionType):
    type = "delete_decoration"
    description = ActionTypeDescription(
        _("Delete decoration"),
        _("View decoration %(decorator_id)s deleted"),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "view_id",
        "table_id",
        "database_id",
        "decorator_id",
        "original_decorator_id",
        "original_decoration_type_name",
        "original_value_provider_type_name",
        "original_value_provider_conf",
        "original_order",
    ]

    @dataclasses.dataclass
    class Params:
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        decorator_id: int
        original_decorator_id: int
        original_decorator_type_name: str
        original_value_provider_type_name: str
        original_value_provider_conf: str
        original_order: int

    @classmethod
    def do(cls, view_decoration: ViewDecoration, user: AbstractUser):
        """
        Deletes an existing view decoration.
        See baserow.contrib.decorations.handler.DecorationsHandler.delete_decoration
        for further details.
        Undoing this action will restore the decoration.
        Redoing this action will delete the decoration again.

        :param view_decoration: The view decoration instance that needs to be deleted.
        :param user: Optional user who have deleted the decoration.
        """

        original_view_decoration = deepcopy(view_decoration)

        ViewHandler().delete_decoration(view_decoration, user=user)

        view = view_decoration.view
        cls.register_action(
            user=user,
            params=cls.Params(
                view.id,
                view.name,
                view.table.id,
                view.table.name,
                view.table.database.id,
                view.table.database.name,
                view_decoration.id,
                original_view_decoration.id,
                original_view_decoration.type,
                original_view_decoration.value_provider_type,
                original_view_decoration.value_provider_conf,
                original_view_decoration.order,
            ),
            scope=cls.scope(view_decoration.view_id),
            workspace=view.table.database.workspace,
        )

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Any, action_being_undone: Action):
        view = ViewHandler().get_view(params.view_id)
        ViewHandler().create_decoration(
            view=view,
            user=user,
            decorator_type_name=params.original_decorator_type_name,
            value_provider_type_name=params.original_value_provider_type_name,
            value_provider_conf=params.original_value_provider_conf,
            primary_key=params.original_decorator_id,
            order=params.original_order,
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Any, action_being_redone: Action):
        view_decoration = ViewHandler().get_decoration(
            user, params.original_decorator_id
        )
        ViewHandler().delete_decoration(view_decoration, user=user)


class CreateViewGroupByActionType(UndoableActionType):
    type = "create_view_group"
    description = ActionTypeDescription(
        _("Create a view group"),
        _('View grouped on field "%(field_name)s" (%(field_id)s)'),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "field_id",
        "view_id",
        "table_id",
        "database_id",
        "view_group_by_id",
        "group_by_order",
        "group_by_width",
    ]

    @dataclasses.dataclass
    class Params:
        field_id: int
        field_name: str
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        view_group_by_id: int
        group_by_order: str
        group_by_width: int
        group_by_type: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        view: View,
        field: Field,
        group_by_order: str,
        group_by_width: int,
        group_by_type: str,
    ) -> ViewGroupBy:
        """
        Creates a new view group_by.
        See baserow.contrib.database.views.handler.ViewHandler.create_group
        for more. When undone the view_group_by is fully deleted from the
        database and when redone it is recreated.

        :param user: The user on whose behalf the view group by is created.
        :param view: The view for which the group by needs to be created.
        :param field: The field that needs to be grouped.
        :param group_by_order: The desired order, can either be ascending (A to Z) or
            descending (Z to A).
        :param group_by_width: The pixel width of the group by.
        :param group_by_type: @TODO docs
        """

        view_group_by = ViewHandler().create_group_by(
            user, view, field, group_by_order, group_by_width, group_by_type
        )

        params = cls.Params(
            field.id,
            field.name,
            view.id,
            view.name,
            view.table.id,
            view.table.name,
            view.table.database.id,
            view.table.database.name,
            view_group_by.id,
            group_by_order,
            group_by_width,
            group_by_type,
        )
        workspace = view.table.database.workspace
        cls.register_action(user, params, cls.scope(view.id), workspace)
        return view_group_by

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        view_group_by = ViewHandler().get_group_by(user, params.view_group_by_id)

        ViewHandler().delete_group_by(user, view_group_by)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        view_handler = ViewHandler()
        field = FieldHandler().get_field(params.field_id)
        view = view_handler.get_view(params.view_id)

        view_handler.create_group_by(
            user,
            view,
            field,
            params.group_by_order,
            params.group_by_width,
            params.group_by_type,
            params.view_group_by_id,
        )


class UpdateViewGroupByActionType(UndoableActionType):
    type = "update_view_group"
    description = ActionTypeDescription(
        _("Update a view group"),
        _('View group by updated on field "%(field_name)s" (%(field_id)s)'),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "field_id",
        "view_id",
        "table_id",
        "database_id",
        "view_group_by_id",
        "group_by_order",
        "group_by_width",
        "group_by_type",
        "original_field_id",
        "original_field_name",
        "original_group_by_order",
        "original_group_by_width",
        "original_group_by_type",
    ]

    @dataclasses.dataclass
    class Params:
        field_id: int
        field_name: str
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        view_group_by_id: int
        group_by_order: str
        group_by_width: int
        group_by_type: str
        original_field_id: int
        original_field_name: str
        original_group_by_order: str
        original_group_by_width: int
        original_group_by_type: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        view_group_by: ViewGroupBy,
        field: Optional[Field] = None,
        order: Optional[str] = None,
        width: Optional[int] = None,
        sort_type: Optional[str] = None,
    ) -> ViewGroupBy:
        """
        Updates the values of an existing view group_by.
        See baserow.contrib.database.views.handler.ViewHandler.update_group
        for more. When undone the view_group_by is restored to it's original state
        and when redone it is updated to it's new state.

        :param user: The user on whose behalf the view group by is updated.
        :param view_group_by: The view group by that needs to be updated.
        :param field: The field that must be grouped on.
        :param order: Indicates the group by order direction.
        :param width: The visual pixel width of the group by.
        :param sort_type: The sort type that must be used, `default` is set as default
            when the sort is created.
        """

        original_field_id = view_group_by.field.id
        original_field_name = view_group_by.field.name
        view_id = view_group_by.view.id
        view_name = view_group_by.view.name
        original_group_by_order = view_group_by.order
        original_group_by_width = view_group_by.width
        original_group_by_type = view_group_by.type

        handler = ViewHandler()
        updated_view_group_by = handler.update_group_by(
            user,
            view_group_by,
            field,
            order,
            width,
            sort_type,
        )

        cls.register_action(
            user=user,
            params=cls.Params(
                updated_view_group_by.field.id,
                updated_view_group_by.field.name,
                view_id,
                view_name,
                updated_view_group_by.view.table.id,
                updated_view_group_by.view.table.name,
                updated_view_group_by.view.table.database.id,
                updated_view_group_by.view.table.database.name,
                updated_view_group_by.id,
                updated_view_group_by.order,
                updated_view_group_by.width,
                updated_view_group_by.type,
                original_field_id,
                original_field_name,
                original_group_by_order,
                original_group_by_width,
                original_group_by_type,
            ),
            scope=cls.scope(view_group_by.view.id),
            workspace=view_group_by.view.table.database.workspace,
        )

        return updated_view_group_by

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        field = FieldHandler().get_field(params.original_field_id)

        view_handler = ViewHandler()
        view_group_by = view_handler.get_group_by(user, params.view_group_by_id)

        view_handler.update_group_by(
            user,
            view_group_by,
            field,
            params.original_group_by_order,
            params.original_group_by_width,
            params.original_group_by_type,
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        field = FieldHandler().get_field(params.field_id)

        view_handler = ViewHandler()
        view_group_by = view_handler.get_group_by(user, params.view_group_by_id)

        view_handler.update_group_by(
            user,
            view_group_by,
            field,
            params.group_by_order,
            params.group_by_width,
            params.group_by_type,
        )


class DeleteViewGroupByActionType(UndoableActionType):
    type = "delete_view_group"
    description = ActionTypeDescription(
        _("Delete a view group"),
        _('View group by deleted from field "%(field_name)s" (%(field_id)s)'),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "field_id",
        "view_id",
        "table_id",
        "database_id",
        "view_group_by_id",
        "group_by_order",
        "group_by_width",
    ]

    @dataclasses.dataclass
    class Params:
        field_id: int
        field_name: str
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        view_group_by_id: int
        group_by_order: str
        group_by_width: int
        group_by_type: str

    @classmethod
    def do(cls, user: AbstractUser, view_group_by: ViewGroupBy):
        """
        Deletes an existing view group_by.
        See baserow.contrib.database.views.handler.ViewHandler.delete_group
        for more. When undone the view_group_by is recreated and when redone
        it is deleted.

        :param user: The user on whose behalf the view group by is deleted.
        :param view_group: The view group by instance that needs
        to be deleted.
        """

        view_group_by_id = view_group_by.id
        view_id = view_group_by.view.id
        view_name = view_group_by.view.name
        field_id = view_group_by.field.id
        field_name = view_group_by.field.name
        group_by_order = view_group_by.order
        group_by_width = view_group_by.width
        group_by_type = view_group_by.type

        ViewHandler().delete_group_by(user, view_group_by)

        params = cls.Params(
            field_id,
            field_name,
            view_id,
            view_name,
            view_group_by.view.table.id,
            view_group_by.view.table.name,
            view_group_by.view.table.database.id,
            view_group_by.view.table.database.name,
            view_group_by_id,
            group_by_order,
            group_by_width,
            group_by_type,
        )
        workspace = view_group_by.view.table.database.workspace
        cls.register_action(user, params, cls.scope(view_group_by.view.id), workspace)

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_to_undo: Action):
        view_handler = ViewHandler()
        view = view_handler.get_view(params.view_id)
        field = FieldHandler().get_field(params.field_id)

        view_handler.create_group_by(
            user,
            view,
            field,
            params.group_by_order,
            params.group_by_width,
            params.group_by_type,
            params.view_group_by_id,
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_to_redo: Action):
        view_group_by = ViewHandler().get_group_by(user, params.view_group_by_id)
        ViewHandler().delete_group_by(user, view_group_by)


class SubmitFormActionType(ActionType):
    type = "submit_form"
    description = ActionTypeDescription(
        _("Submit form"),
        _("Row (%(row_id)s) created via form submission"),
        VIEW_ACTION_CONTEXT,
    )
    analytics_params = [
        "view_id",
        "table_id",
        "database_id",
        "row_id",
    ]

    @dataclasses.dataclass
    class Params:
        view_id: int
        view_name: str
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        row_id: int
        values: Dict[str, Any]
        fields_metadata: dict[str, Any]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        form: FormView,
        values: Dict[str, Any],
        model: Optional[Type[GeneratedTableModel]] = None,
        field_options: Dict[str, Any] | None = None,
    ) -> GeneratedTableModel:
        """
        Submits a form and creates a new row in the table with the provided values.

        :param user: The user of whose behalf the row is created. If an anonymous user
            is submitting the form, the created_by and last_modified_by fields will be
            set to None.
        :param form: The form view that is being submitted.
        :param values: The values that are being submitted to create the row.
        :param model: The table model to use to create the row.
        :param field_options: The form view field options to use to validate values. If
            not provided, the field options will be fetched from the form view.
        :return: The created row instance.
        """

        if form.table.is_read_only_data_synced_table:
            raise CannotCreateRowsInTable(
                "Can't create rows because it has a data sync."
            )

        if model is None:
            model = form.table.get_model()

        row = ViewHandler().submit_form_view(user, form, values, model, field_options)
        rh = RowHandler()
        table = model.baserow_table
        tmodel = table.get_model()
        fields_metadata = rh.get_fields_metadata_for_rows([row], tmodel.get_fields())[
            row.id
        ]
        cache = {}
        serialized_values = {
            f["name"]: f["type"].get_export_serialized_value(
                row, f["name"], cache=cache, files_zip=None, storage=None
            )
            for f in tmodel.get_field_objects()
            if not f["type"].read_only
        }

        workspace = table.database.workspace
        params = cls.Params(
            form.id,
            form.name,
            table.id,
            table.name,
            table.database.id,
            table.database.name,
            row.id,
            serialized_values,
            fields_metadata=fields_metadata,
        )
        cls.register_action(user, params, scope=cls.scope(form.id), workspace=workspace)

        return row

    @classmethod
    def scope(cls, view_id: int) -> ActionScopeStr:
        return ViewActionScopeType.value(view_id)

    @classmethod
    def get_row_change_history(cls, user, action: "ActionData") -> list[RowHistory]:
        params: SubmitFormActionType.Params = cls.serialized_to_params(action.params)
        table_id = params.table_id
        after = params.values
        row_id = params.row_id

        before = {"id": params.row_id}

        if action.command_type == ActionCommandType.UNDO:
            before, after = after, before

        row_history_entries = []
        related_rows_diff: RelatedRowsDiff = defaultdict(
            lambda: defaultdict(lambda: defaultdict(dict))
        )

        def are_equal_on_create(field_identifier, before_value, after_value) -> bool:
            # both fields are empty, but they may
            # be empty in a different way ('' vs None)
            if not before_value and not after_value:
                return True
            return before_value == after_value

        fields_metadata = params.fields_metadata

        if not any(after):
            before = {**before, **after}
        else:
            before = {
                **before,
                **{field_name: "" for field_name in fields_metadata.keys()},
            }

        row_diff = extract_row_diff(
            table_id,
            row_id,
            fields_metadata,
            before,
            after,
            are_equal=are_equal_on_create,
        )

        if row_diff is None:
            row_diff = RowChangeDiff(
                table_id=table_id,
                row_id=row_id,
                changed_field_names=[],
                before_values={},
                after_values={},
            )
            changed_fields_metadata = {}
        else:
            changed_fields_metadata = {
                k: v
                for k, v in fields_metadata.items()
                if k in row_diff.changed_field_names
            }

        entry = construct_entry_from_action_and_diff(
            user,
            action,
            changed_fields_metadata,
            row_diff,
        )
        row_history_entries.append(entry)
        update_related_tables_entries(
            related_rows_diff, changed_fields_metadata, row_diff
        )

        related_entries = construct_related_rows_entries(
            related_rows_diff, user, action
        )
        row_history_entries.extend(related_entries)
        return row_history_entries
