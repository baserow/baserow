from typing import Any

from django.contrib.auth.models import AbstractUser
from django.db import connection, models
from django.db.models import Q
from django.dispatch import Signal
from django.utils.functional import cached_property

from loguru import logger

from baserow.contrib.database.field_rules.registries import (
    FieldRulesTypeRegistry,
    RowRuleChanges,
)
from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow.core.db import specific_iterator

from .collector import FieldRuleCollector
from .exceptions import FieldRuleTableMismatch, NoRuleError
from .models import FieldRule
from .registries import FieldRuleType, field_rules_type_registry
from .signals import field_rule_created, field_rule_deleted, field_rule_updated


class FieldRuleHandler:
    """
    FieldRuleHandler provides an interface to operate on field rules attached to the
    table.
    """

    STATE_COLUMN_NAME = "field_rules_are_valid"

    def __init__(self, table: Table, user: AbstractUser | None = None):
        self.table = table
        self.user = user
        self.collector = FieldRuleCollector(table.get_model())

    def emit_signal(self, signal: Signal, rule: FieldRule):
        """
        Shortcut method that emits a field rules-specific signal after
        a field rule operation.
        """

        signal.send(sender=self.__class__, table=self.table, rule=rule, user=self.user)

    def has_field_rules(self) -> bool:
        """
        Returns `True` if the table contains active field rules.
        """

        if not self.table.field_rules_validity_column_added:
            return False
        return bool(self.applicable_rules_with_types)

    def get_type_handler(self, rule_type_name: str) -> FieldRuleType:
        """
        Returns rule type-specific handler based on a type name.
        """

        return self.registry.get(rule_type_name)

    def get_rule(self, rule_id: int) -> FieldRule:
        """
        Returns a specific rule for a table.
        """

        qs = self._get_bare_rules_queryset()
        try:
            return specific_iterator(qs.filter(id=rule_id))[0].specific
        except IndexError:
            raise NoRuleError()

    def _get_bare_rules_queryset(self) -> models.QuerySet:
        """
        Returns a basic queryset to get table rules.
        """

        field_rule_types_filter = self._get_active_field_rule_types_filter()
        qs = (
            self.table.field_rules.get_queryset()
            .select_related()
            .filter(field_rule_types_filter)
        )
        return qs

    def _get_rules_queryset(self) -> models.QuerySet:
        """
        Returns optimized queryset to get table rules.
        """

        qs = specific_iterator(self._get_bare_rules_queryset())
        return qs

    def get_rules(self) -> list[FieldRule]:
        """
        Returns a list of active rules for a table.
        """

        return [r.specific for r in self._get_rules_queryset()]

    @staticmethod
    def get_state_column() -> models.BooleanField:
        """
        Returns a field to be added to table definition to store information if
        field rule validity column was added to table model.
        """

        return models.BooleanField(
            null=False,
            db_default=True,
            default=True,
            db_index=True,
            help_text="Stores information if a field rules validity column is added",
        )

    def add_state_column(self) -> GeneratedTableModel:
        """
        Adds a state column to the table. State column tells if field rule validity
        column is present in a dynamic model and generated table.
        """

        model = self._get_model()
        if self.table.field_rules_validity_column_added:
            return model

        column = self.get_state_column()
        column.contribute_to_class(model, self.STATE_COLUMN_NAME)
        # atomicity is controlled in the caller
        with connection.schema_editor() as editor:
            editor.add_field(model, column)
        self.table.field_rules_validity_column_added = True
        self.table.save(update_fields=["field_rules_validity_column_added"])

        model = self._get_model()
        return model

    def _set_rule_is_active(self, rule, to_value: bool):
        """
        Update rule.is_active flag value.

        :param rule: FieldRule instance
        :param to_value: target .is_active value
        """

        if rule.is_active == to_value:
            return

        table = rule.table
        if table != self.table:
            return

        rule.is_active = to_value
        rule.save(update_fields=["is_active"])
        self.on_table_change()
        self.emit_signal(field_rule_updated, rule)

    def enable_rule(self, rule):
        """
        Enables a rule.
        """

        self._set_rule_is_active(rule, True)

    def disable_rule(self, rule):
        """
        Disables a rule.
        """

        self._set_rule_is_active(rule, False)

    @property
    def registry(self) -> FieldRulesTypeRegistry:
        """
        A shortcut to get field rule type registry.
        """

        return field_rules_type_registry

    def create_rule(
        self, rule_type_name: str, in_data: dict, primary_key_value: int | None = None
    ) -> FieldRule:
        """
        Creates a rule of a given type.

        This method creates an instance of a field rule. Field rule type is provided
        in `rule_type_name` param. Each field rule type should validate additional
        rule params provided in `in_data` dictionary.

        If `primary_key_value` is provided, the model will receive this specific .id.
        This is used in undo/redo operations, because we want to preserve
        rule identification.

        :param rule_type_name: registered rule type name .
        :param in_data: a dictionary with all rule params.
        :param primary_key_value: (optional) the primary key value for the rule (if
            the instance is being restored).
        :return: rule instance.
        """

        rule_type = self.get_type_handler(rule_type_name)
        model_class = rule_type.model_class

        # Those fields are set explicitly below, so we don't want them in
        # rule payload.
        for k in ("id", "table_id", "is_valid", "error_text"):
            in_data.pop(k, None)

        rule_data = rule_type.prepare_values_for_create(self.table, in_data)
        rule_type.before_rule_created(self.table, rule_data)

        self.add_state_column()

        is_active = rule_data.pop("is_active", True)

        field_rule = model_class.objects.create(
            pk=primary_key_value,
            table=self.table,
            is_active=is_active,
            is_valid=True,
            error_text=None,
            **rule_data,
        )
        rule_type.after_rule_created(field_rule)

        self.on_table_change()
        self.emit_signal(field_rule_created, field_rule)

        return field_rule

    def _update_rule(self, rule: FieldRule, in_data: dict) -> FieldRule:
        """
        Internal update rule routine.
        """

        rule_type: FieldRuleType = rule.get_type()
        is_active = in_data["is_active"]
        if is_active:
            rule.is_active = True
            rule_data = rule_type.prepare_values_for_update(rule, in_data)
            for k, v in rule_data.items():
                setattr(rule, k, v)

            rule_valid = rule_type.validate_rule(rule)

            # Note: this is a workaround to allow any recalculation for the rule
            # after the change.
            if rule_valid.is_valid:
                rule.is_valid = True
            else:
                rule.is_valid = False
                rule.error_text = rule_valid.error_text

            rule.save(
                update_fields=[
                    "is_active",
                    "is_valid",
                    "error_text",
                    *list(rule_data.keys()),
                ]
            )
        elif rule.is_active:  # deactivating the rule
            rule.is_active = False
            rule.save(update_fields=["is_active"])

        rule_type.after_rule_updated(rule)
        return rule

    def update_rule(self, rule: FieldRule, in_data: dict) -> FieldRule:
        """
        Update a specific rule.

        This will call specific rule type handler to get update params, and will
        revalidate all rules in the table.
        """

        if self.table != rule.table:
            raise FieldRuleTableMismatch(
                f"Table {self.table} and rule's table {rule.table} don't match"
            )

        updated = self._update_rule(rule, in_data)
        self.emit_signal(field_rule_updated, updated)

        self.on_table_change()
        return updated

    def on_table_change(self):
        """
        Called when the table schema changes to recheck existing rules, if they are
        still valid.

        A field rule can refer to specific fields in the table, assuming that those
        fields are of a proper type. If any field used by a rule is modified in a way,
        that it's not suitable for the rule, we should mark that the rule is no longer
        valid.

        It will be valid again, if the table will be changed back to proper state.
        """

        self._clear_cache()
        rules = self.applicable_rules_with_types
        for rule, rule_type in rules:
            rule_valid = rule_type.validate_rule(rule)
            if rule.is_valid != rule_valid.is_valid:
                rule.is_valid = rule_valid.is_valid
                rule.error_text = rule.error_text
                rule.save(update_fields=["is_valid", "error_text"])
                self.emit_signal(field_rule_updated, rule)

    def _delete_rule(self, rule: FieldRule):
        """
        Internal delete rule routine.
        """

        rule_type = rule.get_type()
        rule.delete()
        rule_type.after_rule_deleted(rule)

    def delete_rule(self, rule):
        """
        Deletes a rule.
        """

        table = rule.table
        if table != self.table:
            raise FieldRuleTableMismatch()
        self._delete_rule(rule)
        self._clear_cache()
        self.emit_signal(field_rule_deleted, rule)

    def _get_active_field_rule_types_filter(self) -> Q:
        """
        Returns a filter for field rules query that will return field rules that are
        currently supported.
        """

        params = []
        for app_label, model_name in self.registry.get_model_names():
            params.append(
                Q(content_type__app_label=app_label, content_type__model=model_name)
            )
        # model names don't contain `_`
        return Q(*params, _connector=Q.OR)

    @cached_property
    def applicable_rules_with_types(self) -> list[tuple[FieldRule, FieldRuleType]]:
        """
        Returns a list of field rules and rule types that are usable.

        Note: because of pluggability, this may not return rules that are present in the
        database, but have no field rule type registered. A situation like this may
        happen if a field rule was provided by a plugin, that has been removed from
        the deployment.
        """

        out = []
        field_rule_types = self._get_active_field_rule_types_filter()
        queryset = (
            self.table.field_rules.get_queryset()
            .filter(field_rule_types, is_active=True)
            .select_related()
        )

        def per_content_type_queryset_hook(rule, queryset):
            return self.registry.get_by_model(rule).enhance_queryset(queryset, rule)

        for field_rule in specific_iterator(
            queryset, per_content_type_queryset_hook=per_content_type_queryset_hook
        ):
            out.append((field_rule.specific, field_rule.get_type()))
        return out

    def _clear_cache(self):
        """
        Clears internal cache for field rules.
        """

        self.__dict__.pop("applicable_rules_with_types", None)

    def check_table_invalid_rows(self):
        """
        Calls each rule attached to the table to recheck table rows if they are valid
        for those rules.
        """

        rules = self.applicable_rules_with_types
        for rule, rule_type in rules:
            rule_type.validate_rows(self.table, rule)

    def _get_model(self):
        """
        A shortcut to get the table model.
        """

        return self.table.get_model()

    def get_invalid_rows(self) -> models.QuerySet:
        """
        Returns a queryset with rows that have been marked as invalid by any active
        field rule in the table.

        Note: the queryset is optimized to return .id values only.
        """

        return self._get_invalid_rows_query().only("id")

    def _get_invalid_rows_query(self) -> models.QuerySet:
        """
        Returns a queryset with all invalid rows from the table..
        """

        model = self._get_model()
        return model.objects.filter(**{self.STATE_COLUMN_NAME: False})

    def on_rows_create(self, rows_data: list[dict]) -> list[RowRuleChanges]:
        rules = self.applicable_rules_with_types
        collector = self.collector
        model = self._get_model()
        out = []
        for row_data in rows_data:
            changes = self._on_row_create(model, row_data, rules, collector)
            out.extend(changes)
        return out

    def on_row_create(self, row_data) -> list[RowRuleChanges]:
        """
        Called when a row has been created to run all field rules attached to the
        table on that row.

        A rule may change any field in the row, but we don't want to change the row
        directly, so each field rule may return an object with changes that should be
        applied. This method will accumulate those changes into one return value.
        """

        rules = self.applicable_rules_with_types
        collector = self.collector
        model = self._get_model()
        return self._on_row_create(model, row_data, rules, collector)

    def _on_row_create(self, model, row_data, rules, collector) -> list[RowRuleChanges]:
        out = []
        updated_values = {}

        for rule, rule_type in rules:
            updated_rows = rule_type.before_row_created(
                model, row_data, rule, collector
            )
            if not updated_rows:
                continue

            # Note: this assumes that the first row returned from rule type handler will
            # contain new row's updates, if row_id is not provided.
            # The return from the handler may be longer, but other items should be
            # applied to existing rows.
            if updated_rows[0].row_id is None:
                updated_values.update(updated_rows[0].updated_values)
            collector.add_changes(updated_rows)
            out.extend(updated_rows)

        # Apply changes accumulated from rules to row data.
        row_data.update(updated_values)
        return out

    def on_rows_updated(
        self,
        rows: list[GeneratedTableModel],
        updated_values_by_id: dict[int, dict[str, Any]],
    ) -> list[RowRuleChanges]:
        rules = self.applicable_rules_with_types
        collector = self.collector

        out = []
        for row in rows:
            values = updated_values_by_id[row.id]
            changes = self._on_row_update(row, values, rules, collector)
            out.extend(changes)
        # TODO: add row validation for cascades
        return out

    def _on_row_update(
        self, row, updated_values, rules, collector
    ) -> list[RowRuleChanges]:
        out = []
        for rule, rule_type in rules:
            updated_rows = rule_type.before_row_updated(
                row, rule, updated_values, collector
            )
            if not updated_rows:
                continue
            updated_row_values = next(
                (
                    row_change.updated_values
                    for row_change in updated_rows
                    if row_change.row_id == row.id
                ),
                None,
            )
            if updated_row_values:
                updated_values.update(updated_row_values)
                collector.add_changes(updated_rows)
            else:
                logger.error(
                    f"Expected a change for {row} with {rule} rule, "
                    f"but no change found in {updated_rows}."
                )
            out.extend(updated_rows)
        return out

    def on_row_update(
        self, row: GeneratedTableModel, updated_values: dict
    ) -> list[RowRuleChanges]:
        """
        When a row is about to be updated, this method will run all field rules attached
        to the table, to process the change.

        A rule may change any field in the row or in the update, but we don't want to
        change the row directly, so each field rule may return an object with changes
        that should be applied. This method will accumulate those changes into one
        return value.
        """

        rules = self.applicable_rules_with_types
        return self._on_row_update(row, updated_values, rules, self.collector)

    def process_row_update(
        self, updated_values: dict, updated_field_ids: set[int], change: RowRuleChanges
    ):
        """
        Ensures that all fields modified by field rules are added to a provided list of
        updated fields.

        This method is a subsequent part of on_row_create()/on_row_update() calls, if
        the caller requires additional processing of changed row values.
        """

        updated_values.update(change.updated_values)
        for updated_field_id in change.updated_field_ids:
            updated_field_ids.add(updated_field_id)

    def validate_row(self, row: GeneratedTableModel) -> bool:
        """
        Validates if a row conforms all active rules for the table.

        Field rule type handler checks if row values are valid in the context of
        each rule attached to the table. If not, .field_rules_are_valid marker field
        will be set to False for the row. If all rules are valid, the marker will be
        set to True.
        """

        if self.collector.is_starting_row_processed(row):
            return True
        rules = self.applicable_rules_with_types

        for rule, rule_type in rules:
            valid = rule_type.validate_row(row, rule)
            if valid is None:
                continue
            if not valid.is_valid:
                setattr(row, self.STATE_COLUMN_NAME, False)
                return False

        setattr(row, self.STATE_COLUMN_NAME, True)
        return True

    def validate_rows_for_rule(
        self, rule: FieldRule, queryset: models.QuerySet | None = None
    ):
        """
        Validates all rows in the table with a given rule.
        """

        rule_type: FieldRuleType = rule.get_type()
        if not (rule.is_active and rule.is_valid):
            return False

        return rule_type.validate_rows(self.table, rule, queryset=queryset)

    def export_rule(self, rule: FieldRule):
        """
        Exports a rule.
        """

        exportable = rule.is_active and rule.is_valid
        if not exportable:
            return None

        rule_type = rule.get_type()
        rule_data = rule.specific.to_dict()
        return rule_type.prepare_values_for_export(rule_data)

    def import_rule(self, rule_data: dict, id_mapping: dict) -> FieldRule:
        """
        Import rules to a table.
        """

        rule_type_name = rule_data.pop("type")
        rule_type = self.get_type_handler(rule_type_name)

        prepared_values = rule_type.prepare_values_for_import(rule_data, id_mapping)
        return self.create_rule(rule_type_name, prepared_values)
