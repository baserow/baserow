from unittest import mock

from django.db.models import BooleanField

import pytest

from baserow.contrib.database.field_rules.handlers import FieldRuleHandler
from baserow.contrib.database.field_rules.models import FieldRule
from baserow.contrib.database.table.models import GeneratedTableModel
from tests.baserow.contrib.database.utils import DummyFieldRuleType


@pytest.mark.django_db
def test_field_rules_handler_columns(data_fixture, fake_field_rule_registry):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    assert table.field_rules_validity_column_added is False

    fh = FieldRuleHandler(table, user)
    assert not fh.has_field_rules()

    assert isinstance(fh.get_state_column(), BooleanField)

    rule = fh.create_rule("dummy", {})
    assert rule
    table.refresh_from_db()
    assert table.field_rules_validity_column_added is True
    model: GeneratedTableModel = table.get_model()
    state_field = next(
        (f for f in model._meta.fields if f.name == "field_rules_are_valid"), None
    )
    assert state_field


@pytest.mark.django_db
def test_field_rules_handler_type_add_rule(data_fixture, fake_field_rule_registry):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    fh = FieldRuleHandler(table, user)

    rule = fh.create_rule("dummy", {})
    assert rule

    rules = fh.get_rules()
    assert fh.has_field_rules()
    assert len(rules) == 1
    assert isinstance(rules[0], FieldRule)
    rules_and_types = fh.get_applicable_rules_with_types()
    assert len(rules_and_types) == 1
    assert isinstance(rules_and_types[0][0], FieldRule)
    assert isinstance(rules_and_types[0][1], DummyFieldRuleType)
    assert isinstance(fh.get_type_handler(rules[0].get_type().type), DummyFieldRuleType)


@pytest.mark.django_db
def test_field_rules_handler_type_rule_enable_disable(
    data_fixture, fake_field_rule_registry
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    fh = FieldRuleHandler(table, user)

    rule = fh.create_rule("dummy", {})
    assert rule.is_active

    fh.enable_rule(rule)
    rule.refresh_from_db()
    assert rule.is_active

    fh.disable_rule(rule)
    rule.refresh_from_db()
    assert not rule.is_active
    assert fh.get_applicable_rules_with_types() == []

    fh.enable_rule(rule)
    rule.refresh_from_db()
    assert rule.is_active
    assert len(fh.get_applicable_rules_with_types()) == 1


@pytest.mark.django_db
@mock.patch("baserow.contrib.database.field_rules.handlers.field_rule_created.send")
@mock.patch("baserow.contrib.database.field_rules.handlers.field_rule_updated.send")
@mock.patch("baserow.contrib.database.field_rules.handlers.field_rule_deleted.send")
def test_field_rules_handler_type_rule_signals(
    field_rule_deleted_mock,
    field_rule_updated_mock,
    field_rule_added_mock,
    data_fixture,
    fake_field_rule_registry,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    fh = FieldRuleHandler(table, user)
    field_rule_added_mock.assert_not_called()
    field_rule_updated_mock.assert_not_called()
    field_rule_deleted_mock.assert_not_called()

    rule = fh.create_rule("dummy", {})
    field_rule_added_mock.assert_called_once()
    field_rule_updated_mock.assert_not_called()
    field_rule_deleted_mock.assert_not_called()

    fh.update_rule(rule, {"is_active": True})
    field_rule_added_mock.assert_called_once()
    field_rule_updated_mock.assert_called_once()
    field_rule_deleted_mock.assert_not_called()

    fh.delete_rule(rule)
    field_rule_added_mock.assert_called_once()
    field_rule_updated_mock.assert_called_once()
    field_rule_deleted_mock.assert_called_once()


@pytest.mark.django_db
def test_field_rules_handler_type_rule_export_import(
    data_fixture, fake_field_rule_registry
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    fh = FieldRuleHandler(table, user)
    rule = fh.create_rule("dummy", {})
    exported = fh.export_rule(rule)
    assert isinstance(exported, dict)
    assert exported.get("id") == rule.id
    assert exported.get("type") == rule.get_type().type
    assert exported.get("is_active") == rule.is_active
    assert exported.get("table_id") == table.id

    imported = fh.import_rule(exported, {})
    assert isinstance(imported, FieldRule)
    assert imported.id == rule.id + 1
    assert imported.get_type() == rule.get_type()
