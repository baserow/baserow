import dataclasses
from typing import Any

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.contrib.database.action.scopes import (
    TABLE_ACTION_CONTEXT,
    TableActionScopeType,
)
from baserow.contrib.database.fields.models import ButtonField
from baserow.core.action.registries import ActionType, ActionTypeDescription


class DispatchButtonFieldActionType(ActionType):
    """A button click, recorded for the audit log. Not undoable (ADR 006 s.8)."""

    type = "dispatch_button_field"
    description = ActionTypeDescription(
        _("Click button"),
        _('Button "%(field_name)s" (%(field_id)s) clicked on row %(row_id)s'),
        TABLE_ACTION_CONTEXT,
    )
    analytics_params = [
        "table_id",
        "database_id",
        "workspace_id",
        "field_id",
        "action_count",
    ]

    @dataclasses.dataclass
    class Params:
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        workspace_id: int
        workspace_name: str
        field_id: int
        field_name: str
        row_id: int
        action_count: int

    @classmethod
    def do(cls, user: AbstractUser, field: ButtonField, row: Any, action_count: int):
        """
        Records the click.

        :param user: The clicker.
        :param field: The clicked button field.
        :param row: The clicked row, a generated table model instance.
        :param action_count: How many actions the button carried at the click.
        """

        table = field.table
        database = table.database
        workspace = database.workspace
        cls.register_action(
            user,
            cls.Params(
                table.id,
                table.name,
                database.id,
                database.name,
                workspace.id,
                workspace.name,
                field.id,
                field.name,
                row.id,
                action_count,
            ),
            cls.scope(table.id),
            workspace,
        )

    @classmethod
    def scope(cls, table_id: int):
        return TableActionScopeType.value(table_id)
