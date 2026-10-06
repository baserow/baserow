"""The element types Kuma's builder tools treat in their own way."""

from typing import Any

from django.contrib.auth.models import AbstractUser

from baserow.contrib.builder.elements.models import Element, TableElement

from .helpers import ensure_child_menu, resolve_menu_items
from .registries import AssistantElementType, PreparedElementUpdate
from .table_column_changes import merge_table_columns
from .types import ElementUpdate
from .types.element import (
    BUTTON_NAVIGATION_GUIDANCE,
    TABLE_COLUMN_PROPERTIES,
    describe_menu_items,
)
from .types.table_columns import table_column_items


class ButtonAssistantElementType(AssistantElementType):
    """
    Kuma saves a button's label as its value, and points the model to click actions
    for navigation.
    """

    type = "button"

    @property
    def property_aliases(self) -> dict[str, str]:
        """
        The label, which a button saves as its value.

        :return: label, mapped to the value kwarg.
        """

        return {"label": "value"}

    def conflicting_properties(self, update: ElementUpdate) -> list[str]:
        """
        Name the label when it differs from the value, since both set the button's text.

        :param update: The properties to change.
        :return: The label conflict when both are set and differ.
        """

        if (
            update.value is not None
            and update.label is not None
            and update.value != update.label
        ):
            return ["label (conflicts with value)"]
        return []

    def unsupported_guidance(self, supported: set[str]) -> str:
        """
        Explain how to make a button navigate, since that is what the model usually
        tries when it sends a property a button doesn't have.

        :param supported: The properties a button supports.
        :return: How to give a button its navigation.
        """

        return BUTTON_NAVIGATION_GUIDANCE


class LinkAssistantElementType(AssistantElementType):
    """Kuma sets a link's variant and target with link_variant and link_target."""

    type = "link"

    @property
    def property_aliases(self) -> dict[str, str]:
        """
        The link's variant and target, which ElementUpdate prefixes with link_.

        :return: link_variant and link_target, mapped to the variant and target
            kwargs.
        """

        return {"link_variant": "variant", "link_target": "target"}


class ColumnAssistantElementType(AssistantElementType):
    """Kuma sets a column element's alignment with column_alignment."""

    type = "column"

    @property
    def property_aliases(self) -> dict[str, str]:
        """
        The alignment, which ElementUpdate prefixes with column_.

        :return: column_alignment, mapped to the alignment kwarg.
        """

        return {"column_alignment": "alignment"}


class MenuAssistantElementType(AssistantElementType):
    """
    Kuma sets a menu's orientation and alignment with menu_orientation and
    menu_alignment.
    """

    type = "menu"

    @property
    def property_aliases(self) -> dict[str, str]:
        """
        The menu's orientation and alignment, which ElementUpdate prefixes with menu_.

        :return: menu_orientation and menu_alignment, mapped to the orientation and
            alignment kwargs.
        """

        return {"menu_orientation": "orientation", "menu_alignment": "alignment"}

    def prepare_update(
        self, user: AbstractUser, element: Element, update: ElementUpdate
    ) -> PreparedElementUpdate:
        """
        Resolve the sent menu items against the menu's items by uid, so the items
        the update keeps keep their click actions, settings and sub-links.

        :param user: The user updating the menu, who may update it.
        :param element: The menu element, locked for update.
        :param update: The properties to change.
        :return: The menu items to save.
        :raises ToolInputError: When an item can't be applied as sent. Nothing is
            saved.
        """

        if update.menu_items is None:
            return PreparedElementUpdate(kwargs={}, result={})
        menu_items = resolve_menu_items(element.specific, update.menu_items)
        return PreparedElementUpdate(kwargs={"menu_items": menu_items}, result={})

    def item_details(self, element: Element) -> dict[str, Any]:
        """
        Show the menu's items with the uids update_element needs to keep them.

        :param element: The listed menu element.
        :return: Its menu_items.
        """

        return {"menu_items": describe_menu_items(element.specific)}


class MultiPageContainerAssistantElementType(AssistantElementType):
    """
    Kuma sets a header's or footer's menu items on the menu inside it, because
    headers and footers are containers, not menus.
    """

    properties_applied_after_update = frozenset({"menu_items"})

    def after_update(
        self, user: AbstractUser, element: Element, update: ElementUpdate
    ) -> None:
        """
        Set the menu items on the menu inside the element, and create that menu when
        there is none.

        :param user: The user updating the element, who may update it.
        :param element: The updated header or footer.
        :param update: The properties that were changed.
        """

        if update.menu_items is not None:
            ensure_child_menu(user, element, update)


class HeaderAssistantElementType(MultiPageContainerAssistantElementType):
    type = "header"


class FooterAssistantElementType(MultiPageContainerAssistantElementType):
    type = "footer"


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
