import dataclasses

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.contrib.database.action.scopes import (
    TABLE_ACTION_CONTEXT,
    TableActionScopeType,
)
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.core.action.models import Action
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionTypeDescription,
    UndoableActionType,
)

from .handlers import FieldRuleHandler
from .models import FieldRule


class CreateFieldRuleActionType(UndoableActionType):
    type = "create_field_rule"
    description = ActionTypeDescription(
        _("Create Field Rule"),
        _('Table "%(table_name)s": created "%(rule_type)s" field rule'),
        TABLE_ACTION_CONTEXT,
    )
    analytics_params = [
        "database_id",
        "table_id",
        "rule_type",
    ]

    @dataclasses.dataclass
    class Params:
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        rule_id: int
        rule_type: str
        rule_data: dict

    @classmethod
    def do(
        cls, user: AbstractUser, table: Table, rule_type: str, in_rule_data: dict
    ) -> FieldRule:
        """
        Creates a field rule on a table based on the given rule_type.

        A field rule may need various input values, which are passed as `in_rule_data`
        dictionary. It's up to field rule type handler to validate and utilize
        proper values.

        :param user: The user on whose behalf the rule is created.
        :param table: The table on which the rule is created.
        :param rule_type: Requested rule type.
        :param in_rule_data: Rule-type specific parameters.
        :return: FieldRule subclass
        """

        handler = FieldRuleHandler(table, user)
        rule = handler.create_rule(rule_type, in_rule_data)
        params = cls.Params(
            table.id,
            table_name=table.name,
            database_id=table.database.id,
            database_name=table.database.name,
            rule_id=rule.id,
            rule_type=rule_type,
            rule_data=in_rule_data,
        )
        workspace = table.database.workspace
        cls.register_action(user, params, cls.scope(table.id), workspace)

        return rule

    @classmethod
    def scope(cls, table_id) -> ActionScopeStr:
        return TableActionScopeType.value(table_id)

    @classmethod
    def undo(
        cls,
        user: AbstractUser,
        params: Params,
        action_being_undone: Action,
    ):
        table = TableHandler().get_table(params.table_id)
        handler = FieldRuleHandler(table, user)
        rule = handler.get_rule(params.id)
        handler.delete_rule(rule=rule)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        table = TableHandler().get_table(params.table_id)
        handler = FieldRuleHandler(table, user)
        handler.create_rule(
            rule_type_name=params.rule_type,
            in_data=params.rule,
            primary_key_value=params.rule_id,
        )


class UpdateFieldRuleActionType(UndoableActionType):
    type = "update_field_rule"
    description = ActionTypeDescription(
        _("Update field rule"),
        _('Table "%(table_name)s": updated "%(rule_type)s" field rule [%(rule_id)s]'),
        TABLE_ACTION_CONTEXT,
    )
    analytics_params = [
        "database_id",
        "table_id",
        "rule_type",
    ]

    @dataclasses.dataclass
    class Params:
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        rule_id: int
        rule_type: str
        rule_before: dict | None
        rule_after: dict

    @classmethod
    def do(cls, user: AbstractUser, rule: FieldRule, in_rule_data: dict) -> FieldRule:
        """
        Updates a field rule.

        :param user: The user on whose behalf the rule is created.
        :param rule: Specific field rule instance to be updated.
        :param in_rule_data: Rule-type specific parameters.
        :return: FieldRule subclass
        """

        table = rule.table
        handler = FieldRuleHandler(rule.table, user)
        rule_before = rule.to_dict()
        updated = handler.update_rule(rule, in_rule_data)
        params = cls.Params(
            table.id,
            table_name=table.name,
            database_id=table.database.id,
            database_name=table.database.name,
            rule_id=rule.id,
            rule_type=rule.get_type().type,
            rule_before=rule_before,
            rule_after=updated.to_dict(),
        )
        workspace = table.database.workspace
        cls.register_action(user, params, cls.scope(table.id), workspace)

        return updated

    @classmethod
    def scope(cls, table_id) -> ActionScopeStr:
        return TableActionScopeType.value(table_id)

    @classmethod
    def undo(
        cls,
        user: AbstractUser,
        params: Params,
        action_being_undone: Action,
    ):
        table = TableHandler().get_table(params.table_id)
        handler = FieldRuleHandler(table, user)
        rule = handler.get_rule(params.rule_id)
        handler.update_rule(rule, params.rule_before)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        table = TableHandler().get_table(params.table_id)
        handler = FieldRuleHandler(table, user)
        rule = handler.get_rule(params.rule_id)
        handler.update_rule(rule, params.rule_after)


class DeleteFieldRuleActionType(UndoableActionType):
    type = "delete_field_rule"
    description = ActionTypeDescription(
        _("Delete Field rule"),
        _('Table "%(table_name)s": deleted "%(rule_type)s" field rule [%(rule_id)s]'),
        TABLE_ACTION_CONTEXT,
    )
    analytics_params = [
        "database_id",
        "table_id",
        "rule_type",
    ]

    @dataclasses.dataclass
    class Params:
        table_id: int
        table_name: str
        database_id: int
        database_name: str
        rule_id: int
        rule_type: str
        rule_before: dict

    @classmethod
    def do(cls, user: AbstractUser, rule: FieldRule) -> FieldRule:
        """
        Deletes a field rule.

        :param user: The user on whose behalf the rule is removed.
        :param rule: The rule to be removed.
        :returns: FieldRule subclass.
        """

        table = rule.table
        rule_id = rule.id
        handler = FieldRuleHandler(table, user)
        rule_before = rule.to_dict()
        handler.delete_rule(rule)

        params = cls.Params(
            table.id,
            table_name=table.name,
            database_id=table.database.id,
            database_name=table.database.name,
            rule_id=rule_id,
            rule_before=rule_before,
            rule_type=rule.get_type().type,
        )
        workspace = table.database.workspace
        cls.register_action(user, params, cls.scope(table.id), workspace)
        return rule

    @classmethod
    def scope(cls, table_id) -> ActionScopeStr:
        return TableActionScopeType.value(table_id)

    @classmethod
    def undo(
        cls,
        user: AbstractUser,
        params: Params,
        action_being_undone: Action,
    ):
        table = TableHandler().get_table(params.table_id)
        handler = FieldRuleHandler(table, user)
        handler.create_rule(
            rule_type_name=params.rule_type,
            in_data=params.rule,
            primary_key_value=params.rule_id,
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        table = TableHandler().get_table(params.table_id)
        handler = FieldRuleHandler(table, user)
        rule = handler.get_rule(params.id)
        handler.delete_rule(rule=rule)
