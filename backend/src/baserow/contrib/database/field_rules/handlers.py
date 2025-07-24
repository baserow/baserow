from django.db import connection, models, transaction
from django.db.models import Q
from django.dispatch import Signal

from baserow.contrib.database.field_rules.registries import (
    FieldRulesTypeRegistry,
    RowRuleChanges,
)
from baserow.contrib.database.table.cache import clear_generated_model_cache
from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow.core.db import specific_iterator

from .exceptions import FieldRuleTableMismatch, NoRuleError
from .models import FieldRule
from .registries import FieldRuleType, field_rules_type_registry
from .signals import field_rule_created, field_rule_deleted, field_rule_updated


class FieldRuleHandler:
    """
    FieldRuleHandler provides interface to manage field rules.
    """

    STATE_COLUMN_NAME = "field_rules_are_valid"

    def __init__(self, table: Table, user):
        self.table = table
        self.user = user

    def emit_signal(self, signal: Signal, rule):
        signal.send(sender=self.__class__, table=self.table, rule=rule, user=self.user)

    def has_field_rules(self) -> bool:
        if not self.table.field_rules_validity_column_added:
            return False
        return self._get_bare_rules_queryset().exists()

    def get_type_handler(self, rule_type_name: str) -> FieldRuleType:
        return self.registry.get(rule_type_name)

    def get_rule(self, rule_id: int) -> FieldRule:
        qs = self._get_bare_rules_queryset()
        try:
            return specific_iterator(qs.filter(id=rule_id))[0].specific
        except IndexError:
            raise NoRuleError()

    def _get_bare_rules_queryset(self) -> models.QuerySet:
        field_rule_types_filter = self._get_active_field_rule_types_filter()
        qs = (
            self.table.field_rules.get_queryset()
            .filter(field_rule_types_filter)
            .select_related()
        )
        return qs

    def _get_rules_queryset(self) -> models.QuerySet:
        qs = specific_iterator(self._get_bare_rules_queryset())
        return qs

    def get_rules(self) -> list[FieldRule]:
        return [r.specific for r in self._get_rules_queryset()]

    def get_state_column(self):
        return models.BooleanField(
            null=False,
            default=False,
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

        clear_generated_model_cache()
        model = self._get_model()
        return model

    def _toggle_rule(self, rule, to_value: bool):
        """
        Handle a case when a rule is enabled.

        :param rule: FieldRule instance
        :param to_value: target .is_active value
        :return:
        """

        if rule.is_active == to_value:
            return

        table = rule.table
        if table != self.table:
            return

        rule.is_active = to_value
        rule.save(update_fields=["is_active"])
        self.emit_signal(field_rule_updated, rule)
        self.on_table_change()

    def enable_rule(self, rule):
        self._toggle_rule(rule, True)

    def disable_rule(self, rule):
        self._toggle_rule(rule, False)

    @property
    def registry(self) -> FieldRulesTypeRegistry:
        return field_rules_type_registry

    def create_rule(
        self, rule_type_name: str, in_data: dict, primary_key_value: int | None = None
    ) -> FieldRule:
        rule_type = self.get_type_handler(rule_type_name)
        model_class = rule_type.model_class

        with transaction.atomic():
            self.add_state_column()
            rule_data = rule_type.prepare_values_for_create(self.table, in_data)
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
        rule_type: FieldRuleType = rule.get_type()
        rule_data = rule_type.prepare_values_for_update(rule, in_data)
        rule.is_active = in_data["is_active"]
        for k, v in rule_data.items():
            setattr(rule, k, v)
        rule.save(update_fields=["is_active", *list(rule_data.keys())])
        rule_type.after_rule_updated(rule)
        return rule

    def update_rule(self, rule: FieldRule, in_data: dict) -> FieldRule:
        if self.table != rule.table:
            raise FieldRuleTableMismatch(
                f"Table {self.table} and rule's table {rule.table} don't match"
            )

        updated = self._update_rule(rule, in_data)
        self.emit_signal(field_rule_updated, updated)

        self.on_table_change()
        return updated

    def on_table_change(self):
        rules = self.get_applicable_rules_with_types()
        for rule, rule_type in rules:
            rule_valid = rule_type.validate_rule(rule)
            if rule.is_valid != rule_valid.is_valid:
                rule.is_valid = rule_valid.is_valid
                rule.error_text = rule.error_text
                rule.save(update_fields=["is_valid", "error_text"])
                self.emit_signal(field_rule_updated, rule)

    def _delete_rule(self, rule: FieldRule):
        rule_type = rule.get_type()
        rule.delete()
        rule_type.after_rule_deleted(rule)

    def delete_rule(self, rule):
        table = rule.table
        if table != self.table:
            raise FieldRuleTableMismatch()
        self._delete_rule(rule)
        self.emit_signal(field_rule_deleted, rule)

    def _get_active_field_rule_types_filter(self):
        params = []
        for app_label, model_name in self.registry.get_model_names():
            params.append(
                Q(content_type__app_label=app_label, content_type__model=model_name)
            )
        # model names don't contain `_`
        return Q(*params, _connector=Q.OR)

    def get_applicable_rules_with_types(self) -> list[tuple[FieldRule, FieldRuleType]]:
        out = []
        field_rule_types = self._get_active_field_rule_types_filter()
        for field_rule in (
            self.table.field_rules.get_queryset()
            .filter(field_rule_types, is_active=True)
            .select_related()
        ):
            out.append((field_rule.specific, field_rule.get_type()))
        return out

    def check_table_invalid_rows(self):
        rules = self.get_applicable_rules_with_types()
        for rule, rule_type in rules:
            rule_type.validate_rows(self.table, rule)

    def _get_model(self):
        return self.table.get_model()

    def get_invalid_rows(self) -> models.QuerySet:
        return self._get_invalid_rows_query().only("id")

    def _get_invalid_rows_query(self):
        model = self._get_model()
        return model.objects.filter(**{self.STATE_COLUMN_NAME: False})

    def on_row_create(self, row_data) -> RowRuleChanges:
        rules = self.get_applicable_rules_with_types()
        values = {}
        field_ids = set()
        row_id = None
        change = RowRuleChanges(
            row_id=row_id, updated_values=values, updated_field_ids=field_ids
        )
        model = self.table.get_model()
        for rule, rule_type in rules:
            updated_status = rule_type.before_row_created(model, row_data, rule)
            if not updated_status:
                continue
            values.update(updated_status.updated_values)
            [field_ids.add(field_id) for field_id in updated_status.updated_field_ids]

        return change

    def on_row_update(self, row, updated_values) -> RowRuleChanges:
        rules = self.get_applicable_rules_with_types()
        values = {}
        field_ids = set()
        row_id = row.id
        change = RowRuleChanges(
            row_id=row_id, updated_values=values, updated_field_ids=field_ids
        )
        for rule, rule_type in rules:
            updated_status = rule_type.before_row_updated(row, rule, updated_values)
            if not updated_status:
                continue
            values.update(updated_status.updated_values)
            [field_ids.add(field_id) for field_id in updated_status.updated_field_ids]

        return change

    def process_row_update(
        self, updated_values: dict, updated_field_ids: set[int], change: RowRuleChanges
    ):
        updated_values.update(change.updated_values)
        for updated_field_id in change.updated_field_ids:
            updated_field_ids.add(updated_field_id)

    def validate_row(self, row: GeneratedTableModel) -> bool:
        rules = self.get_applicable_rules_with_types()

        for rule, rule_type in rules:
            valid = rule_type.validate_row(row, rule)
            if valid is None:
                return False
            if not valid.is_valid:
                setattr(row, self.STATE_COLUMN_NAME, False)
                return False

        setattr(row, self.STATE_COLUMN_NAME, True)
        return True

    def validate_rows_for_rule(
        self, rule: FieldRule, queryset: models.QuerySet | None = None
    ):
        rule_type: FieldRuleType = rule.get_type()
        if not rule.is_active:
            return False
        if not rule.is_valid:
            return False

        return rule_type.validate_rows(self.table, rule, queryset=queryset)

    def export_rule(self, rule: FieldRule):
        return rule.specific.to_dict()

    def import_rule(self, rule_data: dict, id_mapping: dict) -> FieldRule:
        rule_type_name = rule_data.pop("type")
        rule_type = self.get_type_handler(rule_type_name)
        # remove values that are provided as defaults during rule creation
        for k in ("id", "table_id", "is_valid", "error_text"):
            rule_data.pop(k, None)
        prepared_values = rule_type.prepare_values_for_import(rule_data, id_mapping)
        return self.create_rule(rule_type_name, prepared_values)
