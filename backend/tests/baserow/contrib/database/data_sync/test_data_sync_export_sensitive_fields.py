import pytest

from baserow.contrib.database.data_sync.models import PostgreSQLDataSync
from baserow.contrib.database.data_sync.registries import data_sync_type_registry
from baserow.core.registries import ImportExportConfig


@pytest.mark.django_db
def test_export_serialized_excludes_sensitive_fields(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database, user=user)

    data_sync = PostgreSQLDataSync.objects.create(
        table=table,
        postgresql_host="db.example.com",
        postgresql_username="admin",
        postgresql_password="super-secret-password",
        postgresql_port=5432,
        postgresql_database="mydb",
        postgresql_schema="public",
        postgresql_table="users",
        postgresql_sslmode="prefer",
    )

    data_sync_type = data_sync_type_registry.get("postgresql")
    config = ImportExportConfig(include_permission_data=True)

    serialized = data_sync_type.export_serialized(data_sync, config)

    assert serialized["postgresql_host"] == "db.example.com"
    assert serialized["postgresql_username"] == "admin"
    assert serialized["postgresql_database"] == "mydb"
    assert serialized["postgresql_password"] is None


@pytest.mark.django_db
def test_export_serialized_includes_sensitive_fields_when_not_excluded(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database, user=user)

    data_sync = PostgreSQLDataSync.objects.create(
        table=table,
        postgresql_host="db.example.com",
        postgresql_username="admin",
        postgresql_password="super-secret-password",
        postgresql_port=5432,
        postgresql_database="mydb",
        postgresql_schema="public",
        postgresql_table="users",
        postgresql_sslmode="prefer",
    )

    data_sync_type = data_sync_type_registry.get("postgresql")
    config = ImportExportConfig(
        include_permission_data=True, exclude_sensitive_data=False
    )

    serialized = data_sync_type.export_serialized(data_sync, config)

    assert serialized["postgresql_password"] == "super-secret-password"


@pytest.mark.django_db
def test_export_serialized_without_config_excludes_sensitive_fields(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database, user=user)

    data_sync = PostgreSQLDataSync.objects.create(
        table=table,
        postgresql_host="db.example.com",
        postgresql_username="admin",
        postgresql_password="super-secret-password",
        postgresql_port=5432,
        postgresql_database="mydb",
        postgresql_schema="public",
        postgresql_table="users",
        postgresql_sslmode="prefer",
    )

    data_sync_type = data_sync_type_registry.get("postgresql")

    serialized = data_sync_type.export_serialized(data_sync)

    assert serialized["postgresql_password"] is None


@pytest.mark.django_db
def test_import_serialized_handles_null_password(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database, user=user)
    field = data_fixture.create_text_field(table=table)

    data_sync = PostgreSQLDataSync.objects.create(
        table=table,
        postgresql_host="db.example.com",
        postgresql_username="admin",
        postgresql_password="super-secret-password",
        postgresql_port=5432,
        postgresql_database="mydb",
        postgresql_schema="public",
        postgresql_table="users",
        postgresql_sslmode="prefer",
    )
    data_sync.synced_properties.create(key="id", field=field)

    data_sync_type = data_sync_type_registry.get("postgresql")
    config = ImportExportConfig(include_permission_data=True)

    serialized = data_sync_type.export_serialized(data_sync, config)
    assert serialized["postgresql_password"] is None

    import_table = data_fixture.create_database_table(database=database, user=user)
    import_field = data_fixture.create_text_field(table=import_table)

    id_mapping = {"database_fields": {field.id: import_field.id}}
    imported = data_sync_type.import_serialized(
        import_table, serialized, id_mapping, config
    )

    assert imported.postgresql_host == "db.example.com"
    assert imported.postgresql_password == ""
    assert imported.postgresql_username == "admin"
