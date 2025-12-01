from abc import ABC, abstractmethod
from typing import Any, NamedTuple

from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from baserow.contrib.database.field_rules.collector import FieldRuleCollector
from baserow.contrib.database.field_rules.models import FieldRule
from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow.core.registry import (
    CustomFieldsInstanceMixin,
    CustomFieldsRegistryMixin,
    Instance,
    ModelInstanceMixin,
    ModelRegistryMixin,
    Registry,
)

User = get_user_model()


class RowRuleChanges(NamedTuple):
    row_id: int
    updated_values: dict[str, Any]
    updated_field_ids: set[int]


class RowRuleValidity(NamedTuple):
    row_id: int
    rule_id: int
    is_valid: bool


class FieldRuleValidity(NamedTuple):
    table_id: int
    rule_id: int
    is_valid: bool
    error_text: str


class FieldRuleType(ModelInstanceMixin, CustomFieldsInstanceMixin, Instance, ABC):
    """
    Base class for field rule type hierarchy.

    A subclass defines a behavior of a specific field rule type. A field rule is a
    defined dependency between one or more fields in the table, similar to formulas,
    but allowing the user to change values in fields involved.

    A field rule is attached to a specific table, and one table can contain multiple
    rules. However, not all rules may be usable in a specific moment. Only active and
    valid rules should be used at specific time. Rules in other states should be
    ignored in the processing.

    A user can disable or enable the rule. This is handled by a general update
    mechanism.

    A rule can be marked as invalid. Type handler should provide a method to validate
    a rule.
    """

    model_class = FieldRule

    allowed_fields = [
        "is_active",
        "type",
    ]
    serializer_field_names = [
        "is_active",
        "error_text",
        "is_valid",
        "type",
    ]
    request_serializer_field_names = ["is_active", "type"]

    def enhance_table_queryset(self, queryset) -> QuerySet[Table]:
        """
        Allows to modify table queryset with additional related models
        """

        return queryset

    def enhance_queryset(self, queryset, rule: FieldRule) -> QuerySet[FieldRule]:
        """
        Allows to modify FieldRule queryset with additional related models
        """

        return queryset

    def before_row_updated(
        self,
        row: GeneratedTableModel,
        rule: FieldRule,
        updated_values: dict,
        collector: FieldRuleCollector,
    ) -> list[RowRuleChanges] | None:
        """
        Called during row update, before a row is updated. This will update any
        recalculable fields in the row.
        """

    def before_row_created(
        self,
        model: type[GeneratedTableModel],
        row_data: dict,
        rule: FieldRule,
        collector: FieldRuleCollector,
    ) -> list[RowRuleChanges] | None:
        """
        Called before a row is inserted. This will receive new values only.
        """

    @abstractmethod
    def validate_row(
        self, row: GeneratedTableModel, rule: FieldRule
    ) -> RowRuleValidity:
        """
        Called when a row has been created or changed. This should check, if a row
        conforms the rule. The result says if a specific row for a specific rule
        is valid.
        """

        raise NotImplementedError()

    def after_rule_created(self, rule):
        """
        Called when a rule has been created.
        """

    def after_rule_updated(self, rule):
        """
        Called when a rule has been updated.
        """

    def after_rule_deleted(self, rule):
        """
        Called after a rule has been deleted.
        """

    @abstractmethod
    def validate_rows(
        self, table: Table, rule: FieldRule, queryset: QuerySet | None = None
    ):
        """
        Runs a mass validation of rows for a table for a given rule.
        """

        raise NotImplementedError()

    def prepare_values_for_import(self, rule_data: dict, id_mapping: dict) -> dict:
        """
        Called before creating an imported rule to update import-specific id values
        from import mapping.
        """

        return rule_data

    def prepare_values_for_create(self, table, in_data: dict) -> dict:
        """
        Called before creating a new rule. Resulting dict should contain
        .model_class-specific fields only.
        """

        return in_data

    def prepare_values_for_update(self, rule: FieldRule, in_data: dict) -> dict:
        """
        Called before updating a rule. Resulting dict should contain
        .model_class-specific values
        """

        return in_data

    def before_rule_created(self, table: Table, in_data: dict):
        """
        Called before rule creation.

        Allows field rule type handler to perform additional checks before a rule is
        created.
        """

    def before_rule_deleted(self, rule):
        """
        Called before a rule removal.
        """

    @abstractmethod
    def validate_rule(self, rule: FieldRule) -> FieldRuleValidity:
        """
        A handler should check if a rule is still valid in the context of
        current table.
        """

        raise NotImplementedError()

    def prepare_values_for_export(self, rule_data: dict) -> dict:
        """
        Returns export representation for the rule
        """

        return rule_data


class FieldRulesTypeRegistry(
    ModelRegistryMixin, CustomFieldsRegistryMixin, Registry[FieldRuleType]
):
    name = "field_rules"


field_rules_type_registry = FieldRulesTypeRegistry()
