import dataclasses
from collections.abc import Iterable
from copy import deepcopy
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Type

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from loguru import logger

from baserow.contrib.database.action.scopes import (
    TABLE_ACTION_CONTEXT,
    TableActionScopeType,
)
from baserow.contrib.database.rows.exceptions import (
    CannotCreateRowsInTable,
    CannotDeleteRowsInTable,
)
from baserow.contrib.database.rows.handler import (
    GeneratedTableModelForUpdate,
    RowHandler,
)
from baserow.contrib.database.rows.types import FileImportDict, UpdatedRowsData
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import (
    FieldObject,
    GeneratedTableModel,
    Table,
)
from baserow.contrib.database.views.models import View
from baserow.core.action.models import Action
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionTypeDescription,
    UndoableActionType,
)
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import Progress


def are_equal_on_create(field_identifier, after_value, before_value) -> bool:
    """
    Dummy equal check for created row.

    Some fields require specific types/values to be passed to
    FieldType.are_values_equal().
    At the moment of creation we don't have knowledge what values should be used, but
    that's fine, because all we need is to know if a value inserted is different from
    empty one for a field.
    :param field_identifier:
    :param before_value:
    :param after_value:
    :return:
    """

    # Both field values are empty, but they may be empty in a different way. Initially,
    # we set an empty string for all values, regardless the field type. `after_value`
    # was processed by field type logic and ORM layer, so it can be of a different type,
    # but still an empty value, i.e. `None`.
    if not before_value and not after_value:
        return True
    return before_value == after_value


def get_row_values(
    row: GeneratedTableModel, fields: Iterable[FieldObject]
) -> dict[str, Any]:
    """
    Extracts fields and field values from a row for requested fields.
    """

    rh = RowHandler()
    field_ids = [f["field"].id for f in fields if not f["type"].read_only]
    out = rh.get_internal_values_for_fields(row, field_ids)
    out["id"] = row.id
    return out


class CreateRowActionType(UndoableActionType):
    type = "create_row"
    description = ActionTypeDescription(
        _("Create row"), _("Row (%(row_id)s) created"), TABLE_ACTION_CONTEXT
    )
    analytics_params = [
        "table_id",
        "database_id",
        "row_id",
    ]

    @dataclasses.dataclass
    class Params:
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        row_id: int
        fields_metadata: dict[str, Any]
        row_values: Dict[str, Any]
        view_id: Optional[int] = None
        view_name: Optional[str] = None

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        table: Table,
        values: Optional[Dict[str, Any]] = None,
        model: Optional[Type[GeneratedTableModel]] = None,
        before_row: Optional[GeneratedTableModel] = None,
        view: Optional[View] = None,
        user_field_names: bool = False,
        send_webhook_events: bool = True,
    ) -> GeneratedTableModel:
        """
        Creates a new row for a given table with the provided values if the user
        belongs to the related workspace. It also calls the rows_created signal.
        See the baserow.contrib.database.rows.handler.RowHandler.create_row
        for more information.
        Undoing this action trashes the row and redoing restores it.

        :param user: The user of whose behalf the row is created.
        :param table: The table for which to create a row for.
        :param values: The values that must be set upon creating the row. The keys must
            be the field ids.
        :param model: If a model is already generated it can be provided here to avoid
            having to generate the model again.
        :param before_row: If provided the new row will be placed right before that row
            instance.
        :param view: Optionally provide view, if the row was created in the view.
            This can result in different permissions checks.
        :param user_field_names: Whether or not the values are keyed by the internal
            Baserow field name (field_1,field_2 etc) or by the user field names.
        :param send_webhook_events: If set the false then the webhooks will not be
            triggered. Defaults to true.
        :return: The created row instance.
        """

        if table.is_read_only_data_synced_table:
            raise CannotCreateRowsInTable(
                "Can't create rows because it has a data sync."
            )
        rh = RowHandler()
        row = rh.create_row(
            user,
            table,
            values=values,
            model=model,
            before_row=before_row,
            view=view,
            user_field_names=user_field_names,
            send_webhook_events=send_webhook_events,
        )
        tmodel = table.get_model()
        fields = tmodel.get_field_objects()

        workspace = table.database.workspace
        fields_metadata = rh.get_fields_metadata_for_rows(
            [row],
            [
                f["field"]
                for f in fields
                if f["name"] != "id" and not f["type"].read_only
            ],
        )[row.id]
        row_values = get_row_values(row, fields)
        params = cls.Params(
            table.id,
            table.name,
            table.database.id,
            table.database.name,
            row.id,
            fields_metadata=fields_metadata,
            row_values=row_values,
            view_id=view.id if view else None,
            view_name=view.name if view else None,
        )
        cls.register_action(
            user, params, scope=cls.scope(table.id), workspace=workspace
        )

        return row

    @classmethod
    def scope(cls, table_id) -> ActionScopeStr:
        return TableActionScopeType.value(table_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_being_undone: Action):
        RowHandler().delete_row_by_id(
            user, TableHandler().get_table(params.table_id), params.row_id
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        TrashHandler.restore_item(
            user, "row", params.row_id, parent_trash_item_id=params.table_id
        )


class CreateRowsActionType(UndoableActionType):
    type = "create_rows"
    description = ActionTypeDescription(
        _("Create rows"), _("Rows (%(row_ids)s) created"), TABLE_ACTION_CONTEXT
    )
    analytics_params = [
        "table_id",
        "database_id",
        "trashed_rows_entry_id",
    ]

    @dataclasses.dataclass
    class Params:
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        row_ids: List[int]
        fields_metadata: dict[int, dict[str, Any]]
        rows_values: List[Dict[str, Any]]
        trashed_rows_entry_id: Optional[int] = None
        view_id: Optional[int] = None
        view_name: Optional[str] = None

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        table: Table,
        rows_values: List[Dict[str, Any]],
        before_row: Optional[GeneratedTableModel] = None,
        view: Optional[View] = None,
        model: Optional[Type[GeneratedTableModel]] = None,
        send_webhook_events: bool = True,
    ) -> List[GeneratedTableModel]:
        """
        Creates rows for a given table with the provided values if the user
        belongs to the related workspace. It also calls the rows_created signal.
        See the baserow.contrib.database.rows.handler.RowHandler.create_rows
        for more information.
        Undoing this action trashes the rows and redoing restores them all.

        :param user: The user of whose behalf the rows are created.
        :param table: The table for which the rows should be created.
        :param rows_values: List of rows values for rows that need to be created.
        :param before_row: If provided the new rows will be placed right before
            the row with this id.
        :param view: Optionally provide view, if the rows were created in the view.
            This can result in different permissions checks.
        :param model: If the correct model has already been generated it can be
            provided so that it does not have to be generated for a second time.
        :param send_webhook_events: If set the false then the webhooks will not be
            triggered. Defaults to true.
        :return: The created list of rows instances.
        """

        if table.is_read_only_data_synced_table:
            raise CannotCreateRowsInTable(
                "Can't create rows because it has a data sync."
            )
        rh = RowHandler()
        created_rows = rh.create_rows(
            user,
            table,
            rows_values,
            before_row=before_row,
            view=view,
            model=model,
            send_webhook_events=send_webhook_events,
        )
        rows = created_rows.created_rows

        workspace = table.database.workspace
        tmodel = table.get_model()
        fields = tmodel.get_field_objects()

        fields_metadata = rh.get_fields_metadata_for_rows(
            rows,
            [
                f["field"]
                for f in fields
                if f["name"] != "id" and not f["type"].read_only
            ],
        )
        values = [get_row_values(row, fields) for row in rows]

        params = cls.Params(
            table.id,
            table.name,
            table.database.id,
            table.database.name,
            row_ids=[row.id for row in rows],
            fields_metadata=fields_metadata,
            rows_values=values,
            view_id=view.id if view else None,
            view_name=view.name if view else None,
        )
        cls.register_action(
            user, params, scope=cls.scope(table.id), workspace=workspace
        )

        return rows

    @classmethod
    def scope(cls, table_id) -> ActionScopeStr:
        return TableActionScopeType.value(table_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_being_undone: Action):
        trashed_rows_trash_entry = RowHandler().delete_rows(
            user, TableHandler().get_table(params.table_id), params.row_ids
        )
        params.trashed_rows_entry_id = trashed_rows_trash_entry.id
        action_being_undone.params = params

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        TrashHandler.restore_item(
            user,
            "rows",
            params.trashed_rows_entry_id,
            parent_trash_item_id=params.table_id,
        )


class ImportRowsActionType(UndoableActionType):
    type = "import_rows"
    description = ActionTypeDescription(
        _("Import rows"), _("Rows (%(row_ids)s) imported"), TABLE_ACTION_CONTEXT
    )
    analytics_params = ["table_id", "database_id", "trashed_rows_entry_id"]

    @dataclasses.dataclass
    class Params:
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        row_ids: List[int]
        trashed_rows_entry_id: Optional[int] = None

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        table: Table,
        data: FileImportDict,
        progress: Optional[Progress] = None,
    ) -> Tuple[List[GeneratedTableModel], Dict[str, Any]]:
        """
        Creates rows for a given table with the provided values if the user
        belongs to the related workspace. It also calls the table_updated signal.
        This action is supposed to handle bigger row amount than the createRowsAction,
        it generates an import error report and allow to track the progress.
        Undoing this action trashes the rows and redoing restores them all.
        The new rows are appended to the existing rows.
        See the baserow.contrib.database.rows.handler.RowHandler.import_rows
        for more information.

        :param user: The user of whose behalf the rows are created.
        :param table: The table for which the rows should be imported.
        :param data: List of rows values for rows that need to be created.
        :param progress: An optional progress object to track the task progress.
        :return: The created list of rows instances and the error report.
        """

        if table.is_read_only_data_synced_table:
            raise CannotCreateRowsInTable(
                "Can't create rows because it has a data sync."
            )

        created_rows, error_report = RowHandler().import_rows(
            user,
            table,
            data=data["data"],
            configuration=data.get("configuration") or {},
            progress=progress,
        )
        if error_report:
            logger.warning(f"Errors during rows import: {error_report}")
        workspace = table.database.workspace
        params = cls.Params(
            table.id,
            table.name,
            table.database.id,
            table.database.name,
            [row.id for row in created_rows],
        )
        cls.register_action(
            user, params, scope=cls.scope(table.id), workspace=workspace
        )

        return created_rows, error_report

    @classmethod
    def scope(cls, table_id) -> ActionScopeStr:
        return TableActionScopeType.value(table_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_being_undone: Action):
        trashed_rows_trash_entry = RowHandler().delete_rows(
            user, TableHandler().get_table(params.table_id), params.row_ids
        )
        params.trashed_rows_entry_id = trashed_rows_trash_entry.id
        action_being_undone.params = params

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        TrashHandler.restore_item(
            user,
            "rows",
            params.trashed_rows_entry_id,
            parent_trash_item_id=params.table_id,
        )


class DeleteRowActionType(UndoableActionType):
    type = "delete_row"
    description = ActionTypeDescription(
        _("Delete row"), _("Row (%(row_id)s) deleted"), TABLE_ACTION_CONTEXT
    )
    analytics_params = [
        "table_id",
        "database_id",
        "row_id",
    ]

    @dataclasses.dataclass
    class Params:
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        row_id: int
        values: dict[str, Any]
        fields_metadata: dict[str, Any]
        view_id: Optional[int] = None
        view_name: Optional[str] = None

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        table: Table,
        row_id: int,
        model: Optional[Type[GeneratedTableModel]] = None,
        view: Optional[View] = None,
        send_webhook_events: bool = True,
    ):
        """
        Deletes an existing row of the given table and with row_id.
        See the baserow.contrib.database.rows.handler.RowHandler.delete_row_by_id
        for more information.
        Undoing this action restores the row and redoing trashes it.

        :param user: The user of whose behalf the change is made.
        :param table: The table for which the row must be deleted.
        :param row_id: The id of the row that must be deleted.
        :param model: If the correct model has already been generated, it can be
            provided so that it does not have to be generated for a second time.
        :param view: Optionally provide view, if the row is deleted in the view.
            This can result in different permissions checks.
        :param send_webhook_events: If set the false then the webhooks will not be
            triggered. Defaults to true.
        :raises RowDoesNotExist: When the row with the provided id does not exist.
        """

        if table.is_read_only_data_synced_table:
            raise CannotDeleteRowsInTable(
                "Can't delete rows because it has a data sync."
            )

        rh = RowHandler()
        row = rh.delete_row_by_id(
            user,
            table,
            row_id,
            model=model,
            view=view,
            send_webhook_events=send_webhook_events,
        )

        database = table.database
        tmodel = table.get_model()
        fields = tmodel.get_field_objects()

        fields_metadata = rh.get_fields_metadata_for_rows(
            [row], [f["field"] for f in fields]
        )[row.id]
        params = cls.Params(
            table.id,
            table.name,
            database.id,
            database.name,
            row_id,
            values=get_row_values(row, fields),
            fields_metadata=fields_metadata,
            view_id=view.id if view else None,
            view_name=view.name if view else None,
        )
        cls.register_action(
            user, params, scope=cls.scope(table.id), workspace=database.workspace
        )
        return row

    @classmethod
    def scope(cls, table_id) -> ActionScopeStr:
        return TableActionScopeType.value(table_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_being_undone: Action):
        TrashHandler.restore_item(
            user, "row", params.row_id, parent_trash_item_id=params.table_id
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        RowHandler().delete_row_by_id(
            user, TableHandler().get_table(params.table_id), params.row_id
        )


class DeleteRowsActionType(UndoableActionType):
    type = "delete_rows"
    description = ActionTypeDescription(
        _("Delete rows"), _("Rows (%(row_ids)s) deleted"), TABLE_ACTION_CONTEXT
    )
    analytics_params = [
        "table_id",
        "database_id",
        "trashed_rows_entry_id",
    ]

    @dataclasses.dataclass
    class Params:
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        row_ids: List[int]
        trashed_rows_entry_id: int
        rows_values: list[dict[str, Any]]
        fields_metadata: dict[str, [dict[str, Any]]]
        view_id: Optional[int] = None
        view_name: Optional[str] = None

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        table: Table,
        row_ids: List[int],
        model: Optional[Type[GeneratedTableModel]] = None,
        view: Optional[View] = None,
        send_webhook_events: bool = True,
    ):
        """
        Deletes rows of the given table with the given row_ids.
        See the baserow.contrib.database.rows.handler.RowHandler.delete_rows
        for more information.
        Undoing this action restores the original rows and redoing trashes them again.

        :param user: The user of whose behalf the change is made.
        :param table: The table for which the row must be deleted.
        :param row_ids: The id of the row that must be deleted.
        :param model: If the correct model has already been generated, it can be
            provided so that it does not have to be generated for a second time.
        :param view: Optionally provide view, if the row are deleted in the view.
            This can result in different permissions checks.
        :param send_webhook_events: If set the false then the webhooks will not be
            triggered. Defaults to true.
        :raises RowDoesNotExist: When the row with the provided id does not exist.
        """

        if table.is_read_only_data_synced_table:
            raise CannotDeleteRowsInTable(
                "Can't delete rows because it has a data sync."
            )

        rh = RowHandler()
        trashed_rows_entry = rh.delete_rows(
            user,
            table,
            row_ids,
            model=model,
            view=view,
            send_webhook_events=send_webhook_events,
        )

        workspace = table.database.workspace
        tmodel = table.get_model()
        fields = tmodel.get_field_objects()

        fields_metadata = rh.get_fields_metadata_for_rows(
            trashed_rows_entry.rows, [f["field"] for f in fields]
        )
        rows_values = [get_row_values(row, fields) for row in trashed_rows_entry.rows]
        params = cls.Params(
            table.id,
            table.name,
            table.database.id,
            table.database.name,
            row_ids,
            trashed_rows_entry_id=trashed_rows_entry.id,
            fields_metadata=fields_metadata,
            rows_values=rows_values,
            view_id=view.id if view else None,
            view_name=view.name if view else None,
        )
        cls.register_action(
            user, params, scope=cls.scope(table.id), workspace=workspace
        )
        return trashed_rows_entry

    @classmethod
    def scope(cls, table_id) -> ActionScopeStr:
        return TableActionScopeType.value(table_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_being_undone: Action):
        TrashHandler.restore_item(
            user,
            "rows",
            params.trashed_rows_entry_id,
            parent_trash_item_id=params.table_id,
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        trashed_rows_entry = RowHandler().delete_rows(
            user, TableHandler().get_table(params.table_id), params.row_ids
        )
        params.trashed_rows_entry_id = trashed_rows_entry.id
        action_being_redone.params = params


def get_rows_displacement(
    model: Type[GeneratedTableModel],
    original_row_order: Decimal,
    new_row_order: Decimal,
) -> int:
    """
    Returns the rows count between two row orders.

    :param model: The model of the row.
    :param original_row_order: The row order before move operation.
    :param new_row_order: The row order after move operation.
    """

    def get_displacement(
        lower_order: Decimal,
        higher_order: Decimal,
    ) -> int:
        """Return the rows count between two orders value."""

        return model.objects.filter(
            order__gt=lower_order, order__lt=higher_order
        ).count()

    if new_row_order > original_row_order:
        return get_displacement(original_row_order, new_row_order)
    else:
        return -get_displacement(new_row_order, original_row_order)


def get_before_row_from_displacement(
    row: GeneratedTableModel,
    model: Type[GeneratedTableModel],
    displacement: int,
) -> Optional[GeneratedTableModel]:
    """
    Returns the row instance to use as before in RowHandler().move_row,
    given the displacement.

    :param row: The row instance to use as reference.
    :param model: The model of the row to access data in the table.
    :param displacement: The displacement value.
    """

    if displacement >= 0:
        # a positive displacement means that the row is moved down (bigger order value)
        # so take the row with the order value immediately after the desired position
        try:
            return model.objects.filter(order__gt=row.order).order_by("order")[
                displacement
            ]
        except IndexError:  # after the last line
            return None
    else:
        # displacement < 0 means we are moving the row up (lower order value) but we
        # still need the row with the order value immediately after the desired position
        queryset = model.objects.filter(order__lt=row.order).order_by("-order")
        try:
            # We want to find a row N rows above the provided row, but specifically
            # the before row. The before row is always the row after the slot where
            # we want to move the row. So we minus one from the displacement to get
            # the position instead of this before row.
            return queryset[abs(displacement) - 1]
        except IndexError:
            # cannot be before the first row, so take the first available
            # (the one with the lowest order value as before row).
            return queryset.last()


class MoveRowActionType(UndoableActionType):
    type = "move_row"
    description = ActionTypeDescription(
        _("Move row"), _("Row (%(row_id)s) moved"), TABLE_ACTION_CONTEXT
    )
    analytics_params = ["table_id", "database_id", "row_id", "row_displacement"]

    @dataclasses.dataclass
    class Params:
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        row_id: int
        rows_displacement: int

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        table: Table,
        row_id: int,
        before_row: Optional[GeneratedTableModel] = None,
        model: Optional[Type[GeneratedTableModel]] = None,
        send_webhook_events: bool = True,
    ) -> GeneratedTableModelForUpdate:
        """
        Moves the row before another row or to the end if no before row is provided.
        This moving is done by updating the `order` value of the order.
        See the baserow.contrib.database.rows.handler.RowHandler.move_row
        for more information.
        Undoing this action moves the row back however many positions it was moved
        initially.
        Redoing moves the row in the same direction and number of positions it was
        moved initially.

        :param user: The user of whose behalf the row is moved
        :param table: The table that contains the row that needs to be moved.
        :param row_id: The id of the row that needs to be moved.
        :param before_row: If provided the new row will be placed right before that row
            instance. Otherwise the row will be moved to the end.
        :param model: If the correct model has already been generated, it can be
            provided so that it does not have to be generated for a second time.
        :param send_webhook_events: If set the false then the webhooks will not be
            triggered. Defaults to true.
        """

        if model is None:
            model = table.get_model()

        row_handler = RowHandler()
        row = row_handler.get_row_for_update(user, table, row_id, model=model)

        original_row_order = row.order

        updated_row = row_handler.move_row(
            user,
            table,
            row,
            before_row=before_row,
            model=model,
            send_webhook_events=send_webhook_events,
        )

        rows_displacement = get_rows_displacement(
            model, original_row_order, updated_row.order
        )

        # no need to register the action if the row was not moved
        if rows_displacement == 0:
            return updated_row

        workspace = table.database.workspace
        params = cls.Params(
            table.id,
            table.name,
            table.database.id,
            table.database.name,
            row.id,
            rows_displacement,
        )
        cls.register_action(user, params, cls.scope(table.id), workspace=workspace)
        return updated_row

    @classmethod
    def scope(cls, table_id) -> ActionScopeStr:
        return TableActionScopeType.value(table_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_being_undone: Action):
        table = TableHandler().get_table(params.table_id)
        model = table.get_model()

        row_handler = RowHandler()
        row = row_handler.get_row_for_update(user, table, params.row_id, model=model)

        before_row = get_before_row_from_displacement(
            row, model, -params.rows_displacement
        )

        row_handler.move_row(user, table, row, before_row=before_row, model=model)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        table = TableHandler().get_table(params.table_id)
        model = table.get_model()

        row_handler = RowHandler()
        row = row_handler.get_row_for_update(user, table, params.row_id, model=model)

        before_row = get_before_row_from_displacement(
            row, model, params.rows_displacement
        )

        row_handler.move_row(user, table, row, before_row=before_row, model=model)


# Deprecated in favor of UpdateRowsActionType
class UpdateRowActionType(UndoableActionType):
    type = "update_row"
    description = ActionTypeDescription(
        _("Update row"), _("Row (%(row_id)s) updated"), TABLE_ACTION_CONTEXT
    )
    analytics_params = ["table_id", "database_id", "row_id"]

    @dataclasses.dataclass
    class Params:
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        row_id: int
        row_values: Dict[str, Any]
        original_row_values: Dict[str, Any]
        view_id: Optional[int] = None
        view_name: Optional[str] = None

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        table: Table,
        row_id: int,
        values: Dict[str, Any],
        model: Optional[Type[GeneratedTableModel]] = None,
        view: Optional["View"] = None,
        user_field_names: bool = False,
    ) -> GeneratedTableModelForUpdate:
        """
        Updates one or more values of the provided row_id.
        See the baserow.contrib.database.rows.handler.RowHandler.update_row
        for more information.
        Undoing this action restores the original values.
        Redoing set the new values again.

        :param user: The user of whose behalf the change is made.
        :param table: The table for which the row must be updated.
        :param row_id: The id of the row that must be updated.
        :param values: The values that must be updated. The keys must be the field ids.
        :param model: If the correct model has already been generated it can be
            provided so that it does not have to be generated for a second time.
        :param view: Optionally provide view, if the row is updated in the view.
            This can result in different permissions checks.
        :param user_field_names: Whether or not the values are keyed by the internal
            Baserow field names (field_1,field_2 etc) or by the user field names.
        :raises RowDoesNotExist: When the row with the provided id does not exist.
        :return: The updated row instance.
        """

        if model is None:
            model = table.get_model()

        row_handler = RowHandler()

        if user_field_names:
            values = row_handler.map_user_field_name_dict_to_internal(
                model._field_objects, values
            )

        row = row_handler.get_row_for_update(
            user, table, row_id, enhance_by_fields=True, model=model
        )
        field_ids = set(row_handler.extract_field_ids_from_keys(values.keys()))
        original_row_values = row_handler.get_internal_values_for_fields(row, field_ids)

        updated_row = row_handler.update_row(
            user,
            table,
            row,
            values,
            model=model,
            view=view,
        )
        row_values = row_handler.get_internal_values_for_fields(row, field_ids)

        workspace = table.database.workspace
        params = cls.Params(
            table.id,
            table.name,
            table.database.id,
            table.database.name,
            row.id,
            row_values,
            original_row_values,
            view_id=view.id if view else None,
            view_name=view.name if view else None,
        )
        cls.register_action(
            user, params, scope=cls.scope(table.id), workspace=workspace
        )

        return updated_row

    @classmethod
    def scope(cls, table_id) -> ActionScopeStr:
        return TableActionScopeType.value(table_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_being_undone: Action):
        table = TableHandler().get_table(params.table_id)
        RowHandler().update_row_by_id(
            user, table, row_id=params.row_id, values=params.original_row_values
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        table = TableHandler().get_table(params.table_id)
        RowHandler().update_row_by_id(
            user, table, row_id=params.row_id, values=params.row_values
        )


class UpdateRowsActionType(UndoableActionType):
    type = "update_rows"
    description = ActionTypeDescription(
        _("Update rows"), _("Rows (%(row_ids)s) updated"), TABLE_ACTION_CONTEXT
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
        row_ids: List[int]
        # Note: while `row_values` is a typo, we should not change it, because
        # .Params are used in audit log as well. If this changes, we will need
        # to support both versions of the structure.
        row_values: List[Dict[str, Any]]
        original_rows_values_by_id: Dict[int, Dict[str, Any]]
        updated_fields_metadata_by_row_id: Dict[int, Dict[str, Any]]
        view_id: Optional[int] = None
        view_name: Optional[str] = None

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        table: Table,
        rows_values: List[Dict[str, Any]],
        model: Optional[Type[GeneratedTableModel]] = None,
        view: Optional[View] = None,
        send_webhook_events: bool = True,
    ) -> UpdatedRowsData:
        """
        Updates field values in batch based on provided rows with the new values.
        See the baserow.contrib.database.rows.handler.RowHandler.update_rows
        for more information.
        Undoing this action restores the original values.
        Redoing set the new values again.

        :param user: The user of whose behalf the change is made.
        :param table: The table for which the rows must be updated.
        :param rows_values: The rows values that must be updated. The keys must be the
            field ids plus the id of the row.
        :param model: If the correct model has already been generated it can be
            provided so that it does not have to be generated for a second time.
        :param view: Optionally provide view, if the rows are updated in the view.
            This can result in different permissions checks.
        :param send_webhook_events: If set the false then the webhooks will not be
            triggered. Defaults to true.
        :return: The updated rows.
        """

        row_handler = RowHandler()

        result = row_handler.update_rows(
            user,
            table,
            rows_values,
            model=model,
            view=view,
            send_webhook_events=send_webhook_events,
        )
        updated_rows = result.updated_rows

        workspace = table.database.workspace
        params = cls.Params(
            table.id,
            table.name,
            table.database.id,
            table.database.name,
            [row.id for row in updated_rows],
            result.updated_rows_values,
            result.original_rows_values_by_id,
            result.updated_fields_metadata_by_row_id,
            view_id=view.id if view else None,
            view_name=view.name if view else None,
        )
        cls.register_action(user, params, cls.scope(table.id), workspace=workspace)

        return result

    @classmethod
    def serialized_to_params(cls, serialized_params: Any) -> Any:
        """
        When storing integers as dictionary keys in a database, they are saved
        as strings. This method is designed to convert these string keys back
        into integers. This ensures that we can accurately use the row.id as a
        key."
        """

        serialized_params["original_rows_values_by_id"] = {
            int(row_id): row_values
            for row_id, row_values in serialized_params[
                "original_rows_values_by_id"
            ].items()
        }

        serialized_params["updated_fields_metadata_by_row_id"] = {
            int(row_id): row_values
            for row_id, row_values in serialized_params[
                "updated_fields_metadata_by_row_id"
            ].items()
        }

        return cls.Params(**deepcopy(serialized_params))

    @classmethod
    def scope(cls, table_id) -> ActionScopeStr:
        return TableActionScopeType.value(table_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_being_undone: Action):
        table = TableHandler().get_table(params.table_id)
        original_rows_values = list(params.original_rows_values_by_id.values())
        RowHandler().update_rows(user, table, original_rows_values)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        table = TableHandler().get_table(params.table_id)
        RowHandler().update_rows(user, table, params.row_values)
