import dataclasses
from typing import Optional

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow_premium.fields.handler import AIFieldHandler

from baserow.contrib.database.action.scopes import (
    TABLE_ACTION_CONTEXT,
    TableActionScopeType,
)
from baserow.contrib.database.table.models import Table
from baserow.core.action.registries import ActionType, ActionTypeDescription


class GenerateFormulaWithAIActionType(ActionType):
    type = "generate_formula_with_ai"
    description = ActionTypeDescription(
        _("Generate Formula With AI"),
        _('Generate formula with AI using "%(ai_type)s" and "%(ai_model)s"'),
        TABLE_ACTION_CONTEXT,
    )
    analytics_params = ["table_id", "database_id", "ai_type", "ai_model"]

    @dataclasses.dataclass
    class Params:
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        ai_type: str
        ai_model: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        table: Table,
        ai_type: str,
        ai_model: str,
        ai_prompt: str,
        ai_temperature: Optional[float] = None,
    ):
        formula = AIFieldHandler.generate_formula_with_ai(
            table, ai_type, ai_model, ai_prompt, ai_temperature=ai_temperature
        )
        database = table.database
        workspace = database.workspace

        cls.register_action(
            user,
            cls.Params(
                table.id,
                table.name,
                database.id,
                database.name,
                ai_type,
                ai_model,
            ),
            cls.scope(workspace.id),
            workspace,
        )

        return formula

    @classmethod
    def scope(cls, table_id: int):
        return TableActionScopeType.value(table_id)
