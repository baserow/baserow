"""The element types Kuma's builder tools treat in their own way."""

from typing import Any

from django.contrib.auth.models import AbstractUser

from baserow.contrib.builder.elements.models import Element, MenuElement, TableElement
from baserow.contrib.builder.workflow_actions.models import NotificationWorkflowAction
from baserow.core.tools.errors import ToolInputError

from .formulas import current_record_of, formula_problem, page_formula_context
from .helpers import child_menu, page_parameters_problem, save_child_menu
from .menu_item_changes import MenuItemsChange, linkable_page_ids, merge_menu_items
from .registries import AssistantElementType, PreparedElementUpdate
from .table_column_changes import merge_table_columns
from .types import ElementUpdate
from .types.changes import NO_CHANGES
from .types.element import (
    BUTTON_NAVIGATION_GUIDANCE,
    MENU_ITEM_PROPERTIES,
    TABLE_COLUMN_PROPERTIES,
)
from .types.menu_items import listed_menu_items
from .types.table_columns import stored_formula_text, table_column_items


def _merge_menu_item_changes(
    menu: MenuElement | None, element: Element, update: ElementUpdate
) -> MenuItemsChange:
    """
    Merge an update's menu item changes into a menu's saved items.

    :param menu: The menu, or None when a header or footer has no menu yet.
    :param element: The updated menu, header or footer, whose builder's pages the
        items may link to.
    :param update: The update holding the changes.
    :return: The items to save and the items removed.
    :raises ToolInputError: When a change can't be applied; nothing is saved.
    """

    return merge_menu_items(
        menu,
        page_ids=linkable_page_ids(element.page.builder_id),
        add=update.add_menu_items or [],
        update=update.update_menu_items or [],
        reorder=update.reorder_menu_items,
        remove=update.remove_menu_items or [],
    )


def _removed_result(change: MenuItemsChange) -> dict[str, Any]:
    return {"removed_menu_items": change.removed} if change.removed else {}


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

    def updated_result(self, element: Element, update: ElementUpdate) -> dict[str, Any]:
        """
        Say that a new text left the message the button shows when clicked as it was,
        since both can be meant by "the message of the button".

        :param element: The updated button.
        :param update: The properties that were changed.
        :return: A note naming the button's notifications when its text changed.
        """

        if update.value is None and update.label is None:
            return {}
        notifications = [
            f"action {action.id}, title {action.title['formula']}"
            for action in NotificationWorkflowAction.objects.filter(element=element)
        ]
        if not notifications:
            return {}
        return {
            "note": (
                "This changed only the text on the button. Clicking it also shows a "
                f"notification ({'; '.join(notifications)}), which stays as it was. "
                "If that message is what should change, use update_action."
            )
        }


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

    def prepare_update(
        self, user: AbstractUser, element: Element, update: ElementUpdate
    ) -> PreparedElementUpdate:
        """
        Check that a new target page fits the parameters the link has, which an update
        can't change.

        :raises ToolInputError: When they don't fit. Nothing is saved.
        """

        page_id = update.navigate_to_page_id
        if page_id is not None and page_id != element.navigate_to_page_id:
            problem = page_parameters_problem(
                element.page.builder_id,
                page_id,
                [param["name"] for param in element.page_parameters or []],
            )
            if problem:
                raise ToolInputError(
                    f"{problem} {NO_CHANGES} To link to that page, create a new link "
                    "with link_page_parameters. This one stays on the page until "
                    "someone deletes it in the editor."
                )
        return super().prepare_update(user, element, update)


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
    menu_alignment, and changes its items by uid.
    """

    type = "menu"

    @property
    def property_aliases(self) -> dict[str, str]:
        """
        The menu's orientation and alignment, which ElementUpdate prefixes with menu_,
        and the menu item changes, which are all saved as the menu's items.

        :return: menu_orientation and menu_alignment, mapped to the orientation and
            alignment kwargs, and each menu item change, mapped to the menu_items
            kwarg.
        """

        return {
            "menu_orientation": "orientation",
            "menu_alignment": "alignment",
            **dict.fromkeys(MENU_ITEM_PROPERTIES, "menu_items"),
        }

    def prepare_update(
        self, user: AbstractUser, element: Element, update: ElementUpdate
    ) -> PreparedElementUpdate:
        """
        Merge the menu item changes into the saved items, so the items they don't
        name are saved unchanged.

        :param user: The user updating the menu, who may update it.
        :param element: The menu element, locked for update.
        :param update: The properties to change.
        :return: The full item list to save, and the removed items when there are
            any.
        :raises ToolInputError: When a change can't be applied. Nothing is saved.
        """

        if not update.changes_menu_items():
            return PreparedElementUpdate(kwargs={}, result={})
        change = _merge_menu_item_changes(element.specific, element, update)
        return PreparedElementUpdate(
            kwargs={"menu_items": change.menu_items}, result=_removed_result(change)
        )

    def updated_result(self, element: Element, update: ElementUpdate) -> dict[str, Any]:
        """
        Read the menu's items again after a menu item change.

        :param element: The updated menu element.
        :param update: The properties that were changed.
        :return: The menu's items when the update changed them.
        """

        if not update.changes_menu_items():
            return {}
        return {"menu_items": listed_menu_items(MenuElement.objects.get(id=element.id))}

    def item_details(self, element: Element) -> dict[str, Any]:
        """
        Show the menu's items with the uids update_element changes them by.

        :param element: The listed menu element.
        :return: Its menu_items.
        """

        return {"menu_items": listed_menu_items(element.specific)}


class MultiPageContainerAssistantElementType(AssistantElementType):
    """
    Kuma changes a header's or footer's menu items on the menu inside it, because
    headers and footers are containers, not menus.
    """

    properties_applied_after_update = frozenset(MENU_ITEM_PROPERTIES)

    def after_update(
        self, user: AbstractUser, element: Element, update: ElementUpdate
    ) -> dict[str, Any]:
        """
        Apply the menu item changes to the menu inside the element, at any depth,
        creating that menu when there is none.

        :param user: The user updating the element, who may update it.
        :param element: The updated header or footer.
        :param update: The properties that were changed.
        :return: The menu's items after the change and the removed items, when the
            update changed menu items.
        :raises ToolInputError: When a change can't be applied or the element holds
            more than one menu. update_element's transaction then saves nothing.
        """

        if not update.changes_menu_items():
            return {}
        menu = child_menu(element)
        change = _merge_menu_item_changes(menu, element, update)
        saved = save_child_menu(user, element, menu, change.menu_items)
        return {
            "menu_items": listed_menu_items(MenuElement.objects.get(id=saved.id)),
            **_removed_result(change),
        }


class HeaderAssistantElementType(MultiPageContainerAssistantElementType):
    type = "header"


class FooterAssistantElementType(MultiPageContainerAssistantElementType):
    type = "footer"


def _check_changed_column_formulas(
    table: TableElement, columns: list[dict[str, Any]]
) -> None:
    """
    Check the values and labels a change adds or alters. The other columns stay out
    of it, so what is already stored can't block an unrelated edit.

    :param table: The table element, with its columns as they are stored.
    :param columns: The full column list that would be saved.
    :raises ToolInputError: When one of them can't be read on the table's page.
    """

    stored = {str(column.uid): column.config for column in table.fields.all()}
    changed = [
        (f"{key} of column {column['name']}", text)
        for column in columns
        for key in ("value", "label")
        if (text := stored_formula_text(column["config"], key))
        and text != stored_formula_text(stored.get(column.get("uid")), key)
    ]
    if not changed:
        return
    context = page_formula_context(table.page)
    with current_record_of(context, "element", table):
        for field, formula in changed:
            problem = formula_problem(field, formula, context)
            if problem:
                raise ToolInputError(f"{problem} {NO_CHANGES}")


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
        :raises ToolInputError: When a column change can't be applied or a new or
            changed column reads something the page doesn't have. Nothing is saved.
        """

        if not update.changes_table_columns():
            return PreparedElementUpdate(kwargs={}, result={})
        table = element.specific
        change = merge_table_columns(
            table,
            add=update.add_table_columns or [],
            update=update.update_table_columns or [],
            reorder=update.reorder_table_columns,
            remove=update.remove_table_columns or [],
        )
        _check_changed_column_formulas(table, change.fields)
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
