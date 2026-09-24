import pytest

from baserow.contrib.database.field_rules.handlers import FieldRuleHandler
from baserow.contrib.database.field_rules.models import FieldRule
from baserow.core.registries import ImportExportConfig, application_type_registry


def _create_table_with_rule(data_fixture, is_valid: bool):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, name="text")

    rule = FieldRuleHandler(table, user).create_rule("dummy", {})
    FieldRule.objects.filter(id=rule.id).update(is_valid=is_valid)
    return user, database, table


@pytest.mark.django_db
def test_export_serialized_skips_invalid_field_rules(
    data_fixture, fake_field_rule_registry
):
    user, database, table = _create_table_with_rule(data_fixture, is_valid=False)

    database_type = application_type_registry.get("database")
    config = ImportExportConfig(include_permission_data=True)
    serialized = database_type.export_serialized(database, config)

    assert serialized["tables"][0]["field_rules"] == []


@pytest.mark.django_db
def test_import_serialized_with_invalid_field_rule(
    data_fixture, fake_field_rule_registry
):
    user, database, table = _create_table_with_rule(data_fixture, is_valid=False)

    database_type = application_type_registry.get("database")
    config = ImportExportConfig(include_permission_data=True)
    serialized = database_type.export_serialized(database, config)

    imported_workspace = data_fixture.create_workspace(user=user)
    imported_database = database_type.import_serialized(
        imported_workspace, serialized, config, {}, None, None
    )

    imported_table = imported_database.table_set.get()
    assert not FieldRule.objects.filter(table=imported_table).exists()


@pytest.mark.django_db
def test_import_serialized_with_valid_field_rule(
    data_fixture, fake_field_rule_registry
):
    user, database, table = _create_table_with_rule(data_fixture, is_valid=True)

    database_type = application_type_registry.get("database")
    config = ImportExportConfig(include_permission_data=True)
    serialized = database_type.export_serialized(database, config)

    assert [r["type"] for r in serialized["tables"][0]["field_rules"]] == ["dummy"]

    imported_workspace = data_fixture.create_workspace(user=user)
    imported_database = database_type.import_serialized(
        imported_workspace, serialized, config, {}, None, None
    )

    imported_table = imported_database.table_set.get()
    assert FieldRule.objects.filter(table=imported_table).count() == 1
