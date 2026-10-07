"""The element types Kuma's builder tools treat in their own way."""

from typing import Any

from django.contrib.auth.models import AbstractUser

from baserow.contrib.builder.elements.models import Element, TableElement

from .registries import AssistantElementType, PreparedElementUpdate
from .table_column_changes import merge_table_columns
from .types import ElementUpdate
from .types.element import TABLE_COLUMN_PROPERTIES
from .types.table_columns import table_column_items


class TableAssistantElementType(AssistantElementType):
    """Kuma lists a table's columns, changes them by uid and reads them back."""

    type = "table"

    @property
    def property_aliases(self) -> dict[str, str]:
        """
        The table column changes, which are all saved as the table's columns.

        :return: Each column change property, mapped to the fields kwarg.
        """

        return dict.fromkeys(TABLE_COLUMN_PROPERTIES, "fields")

    def prepare_update(
        self, user: AbstractUser, element: Element, update: ElementUpdate
    ) -> PreparedElementUpdate:
        """
        Merge the column changes into the stored columns, so the columns they don't
        name are saved unchanged.

        :param user: The user updating the table, who may update it.
        :param element: The table element, locked for update.
        :param update: The properties to change.
        :return: The full column list to save, and the removed columns when there
            are any.
        :raises ToolInputError: When a column change can't be applied. Nothing is
            saved.
        """

        if not update.changes_table_columns():
            return PreparedElementUpdate(kwargs={}, result={})
        change = merge_table_columns(
            element.specific,
            add=update.add_table_columns or [],
            update=update.update_table_columns or [],
            reorder=update.reorder_table_columns,
            remove=update.remove_table_columns or [],
        )
        result = {"removed_table_columns": change.removed} if change.removed else {}
        return PreparedElementUpdate(kwargs={"fields": change.fields}, result=result)

    def updated_result(self, element: Element, update: ElementUpdate) -> dict[str, Any]:
        """
        Read the table's columns again after a column change.

        :param element: The updated table element.
        :param update: The properties that were changed.
        :return: The table's columns when the update changed them.
        """

        if not update.changes_table_columns():
            return {}
        table = TableElement.objects.prefetch_related("fields").get(id=element.id)
        return {"table_columns": table_column_items(table)}

    def item_details(self, element: Element) -> dict[str, Any]:
        """
        Show the data source a table reads and its columns.

        :param element: The listed table element.
        :return: Its data_source_id and table_columns.
        """

        table = element.specific
        return {
            "data_source_id": table.data_source_id,
            "table_columns": table_column_items(table),
        }
