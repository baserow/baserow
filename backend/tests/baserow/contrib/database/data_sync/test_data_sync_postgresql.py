from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.db import connection, transaction
from django.test.utils import override_settings
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.database.data_sync.exceptions import SyncError
from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.models import (
    DataSync,
    PostgreSQLDataSync,
    SyncDataSyncTableJob,
)
from baserow.contrib.database.data_sync.postgresql_data_sync_type import (
    TextPostgreSQLSyncProperty,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import NumberField
from baserow.core.db import specific_iterator


@pytest.mark.django_db(transaction=True)
def test_create_postgresql_data_sync(data_fixture, create_postgresql_test_table):
    default_database = settings.DATABASES["default"]
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        synced_properties=[
            "id",
            "text_col",
            "char_col",
            "int_col",
            "numeric_col",
            "numeric2_col",
            "smallint_col",
            "bigint_col",
            "decimal_col",
            "date_col",
            "datetime_col",
            "boolean_col",
        ],
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=create_postgresql_test_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )

    assert isinstance(data_sync, PostgreSQLDataSync)
    assert data_sync.postgresql_host == default_database["HOST"]
    assert data_sync.postgresql_username == default_database["USER"]
    assert data_sync.postgresql_password == default_database["PASSWORD"]
    assert data_sync.postgresql_database == default_database["NAME"]
    assert data_sync.postgresql_port == default_database["PORT"]
    assert data_sync.postgresql_schema == "public"
    assert data_sync.postgresql_table == create_postgresql_test_table
    assert data_sync.postgresql_sslmode == default_database["OPTIONS"].get(
        "sslmode", "prefer"
    )

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 12
    assert fields[0].name == "id 2"
    assert isinstance(fields[0], NumberField)
    assert fields[0].primary is True
    assert fields[0].read_only is True
    assert fields[0].immutable_type is True
    assert fields[0].immutable_properties is False
    assert fields[0].number_decimal_places == 0


@pytest.mark.django_db(transaction=True)
def test_sync_postgresql_data_sync(data_fixture, create_postgresql_test_table):
    default_database = settings.DATABASES["default"]
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        synced_properties=[
            "id",
            "text_col",
            "char_col",
            "int_col",
            "float_col",
            "numeric_col",
            "numeric2_col",
            "smallint_col",
            "bigint_col",
            "decimal_col",
            "date_col",
            "datetime_col",
            "boolean_col",
        ],
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=create_postgresql_test_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )

    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    id_field = fields[0]
    text_field = fields[1]
    char_field = fields[2]
    int_field = fields[3]
    float_field = fields[4]
    numeric_field = fields[5]
    numeric2_field = fields[6]
    smallint_field = fields[7]
    bigint_field = fields[8]
    decimal_field = fields[9]
    date_field = fields[10]
    datetime_field = fields[11]
    boolean_field = fields[12]

    model = data_sync.table.get_model()
    rows = list(model.objects.all())
    assert len(rows) == 2
    filled_row = rows[0]
    empty_row = rows[1]

    assert getattr(filled_row, f"field_{id_field.id}") == 1
    assert (
        getattr(filled_row, f"field_{text_field.id}")
        == "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Maecenas non nunc et sapien ultricies blandit. "
    )
    assert getattr(filled_row, f"field_{char_field.id}") == "Short char"
    assert getattr(filled_row, f"field_{int_field.id}") == 10
    # Decimal places are not set if no scale is provided in the column type.
    assert getattr(filled_row, f"field_{float_field.id}") == Decimal("10")
    assert getattr(filled_row, f"field_{numeric_field.id}") == 100
    # Decimal places should be set because it's defined in column type.
    assert getattr(filled_row, f"field_{numeric2_field.id}") == Decimal("10.4444")
    assert getattr(filled_row, f"field_{smallint_field.id}") == 200
    assert getattr(filled_row, f"field_{bigint_field.id}") == 99999999
    # Decimal places are not set if no scale is provided in the column type.
    assert getattr(filled_row, f"field_{decimal_field.id}") == Decimal("99999999")
    assert getattr(filled_row, f"field_{date_field.id}") == date(2023, 1, 17)
    assert getattr(filled_row, f"field_{datetime_field.id}") == datetime(
        2022, 2, 28, 12, 0, tzinfo=timezone.utc
    )
    assert getattr(filled_row, f"field_{boolean_field.id}") is True

    assert getattr(empty_row, f"field_{id_field.id}") == 2
    assert getattr(empty_row, f"field_{text_field.id}") is None
    assert getattr(empty_row, f"field_{char_field.id}") is None
    assert getattr(empty_row, f"field_{int_field.id}") is None
    assert getattr(empty_row, f"field_{float_field.id}") is None
    assert getattr(empty_row, f"field_{numeric_field.id}") is None
    assert getattr(empty_row, f"field_{numeric2_field.id}") is None
    assert getattr(empty_row, f"field_{smallint_field.id}") is None
    assert getattr(empty_row, f"field_{bigint_field.id}") is None
    assert getattr(empty_row, f"field_{decimal_field.id}") is None
    assert getattr(empty_row, f"field_{date_field.id}") is None
    assert getattr(empty_row, f"field_{datetime_field.id}") is None
    assert getattr(empty_row, f"field_{boolean_field.id}") is False


@pytest.mark.django_db(transaction=True)
def test_sync_postgresql_data_sync_nothing_changed(
    data_fixture, create_postgresql_test_table
):
    default_database = settings.DATABASES["default"]
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        synced_properties=[
            "id",
            "text_col",
            "char_col",
            "int_col",
            "float_col",
            "numeric_col",
            "numeric2_col",
            "smallint_col",
            "bigint_col",
            "decimal_col",
            "date_col",
            "datetime_col",
            "boolean_col",
        ],
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=create_postgresql_test_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )

    with transaction.atomic():
        handler.sync_data_sync_table(user=user, data_sync=data_sync)

    model = data_sync.table.get_model()
    rows = list(model.objects.all())
    row_1 = rows[0]
    row_2 = rows[1]

    row_1_last_modified = row_1.updated_on
    row_2_last_modified = row_2.updated_on

    with transaction.atomic():
        handler.sync_data_sync_table(user=user, data_sync=data_sync)

    row_1.refresh_from_db()
    row_2.refresh_from_db()

    # Because none of the values have changed in the source (interesting) table,
    # we don't expect the rows to have been updated. If they have been updated,
    # it means that the `is_equal` method of `BaserowFieldDataSyncProperty` is not
    # working as expected.
    assert row_1.updated_on == row_1_last_modified
    assert row_2.updated_on == row_2_last_modified


@pytest.mark.django_db(transaction=True)
def test_sync_postgresql_data_sync_auto_add_new_properties(
    data_fixture, create_postgresql_test_table
):
    default_database = settings.DATABASES["default"]
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        auto_add_new_properties=True,
        synced_properties=[
            "id",
            "text_col",
            "char_col",
            "int_col",
            "float_col",
            "numeric_col",
            "numeric2_col",
            "smallint_col",
            "bigint_col",
            "decimal_col",
            "date_col",
            "datetime_col",
            "boolean_col",
        ],
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=create_postgresql_test_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )

    with transaction.atomic():
        handler.sync_data_sync_table(user=user, data_sync=data_sync)

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                ALTER TABLE {create_postgresql_test_table} ADD COLUMN new_col TEXT;
            """
            )

    with transaction.atomic():
        handler.sync_data_sync_table(user=user, data_sync=data_sync)

    data_sync.refresh_from_db()
    synced_properties = [field.name for field in data_sync.table.field_set.all()]
    assert "new_col" in synced_properties


@pytest.mark.django_db(transaction=True)
def test_postgresql_data_sync_get_properties(
    data_fixture, api_client, create_postgresql_test_table
):
    default_database = settings.DATABASES["default"]
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:database:data_sync:properties")
    response = api_client.post(
        url,
        {
            "type": "postgresql",
            "postgresql_host": default_database["HOST"],
            "postgresql_username": default_database["USER"],
            "postgresql_password": default_database["PASSWORD"],
            "postgresql_port": default_database["PORT"],
            "postgresql_database": default_database["NAME"],
            "postgresql_table": create_postgresql_test_table,
            "postgresql_sslmode": default_database["OPTIONS"].get("sslmode", "prefer"),
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == [
        {
            "unique_primary": True,
            "key": "id",
            "name": "id",
            "field_type": "number",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "text_col",
            "name": "text_col",
            "field_type": "long_text",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "char_col",
            "name": "char_col",
            "field_type": "text",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "int_col",
            "name": "int_col",
            "field_type": "number",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "float_col",
            "name": "float_col",
            "field_type": "number",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "numeric_col",
            "name": "numeric_col",
            "field_type": "number",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "numeric2_col",
            "name": "numeric2_col",
            "field_type": "number",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "smallint_col",
            "name": "smallint_col",
            "field_type": "number",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "bigint_col",
            "name": "bigint_col",
            "field_type": "number",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "decimal_col",
            "name": "decimal_col",
            "field_type": "number",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "date_col",
            "name": "date_col",
            "field_type": "date",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "datetime_col",
            "name": "datetime_col",
            "field_type": "date",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "boolean_col",
            "name": "boolean_col",
            "field_type": "boolean",
            "initially_selected": True,
        },
    ]


@pytest.mark.django_db(transaction=True)
def test_postgresql_data_sync_get_properties_unsupported_column_types(
    data_fixture, api_client, create_postgresql_test_table
):
    default_database = settings.DATABASES["default"]
    user, token = data_fixture.create_user_and_token()

    with patch(
        "baserow.contrib.database.data_sync.postgresql_data_sync_type.column_type_to_baserow_field_type",
        new={
            "char": TextPostgreSQLSyncProperty,
        },
    ):
        url = reverse("api:database:data_sync:properties")
        response = api_client.post(
            url,
            {
                "type": "postgresql",
                "postgresql_host": default_database["HOST"],
                "postgresql_username": default_database["USER"],
                "postgresql_password": default_database["PASSWORD"],
                "postgresql_port": default_database["PORT"],
                "postgresql_database": default_database["NAME"],
                "postgresql_table": create_postgresql_test_table,
                "postgresql_sslmode": default_database["OPTIONS"].get(
                    "sslmode", "prefer"
                ),
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK
    assert response.json() == [
        {
            "unique_primary": False,
            "key": "char_col",
            "name": "char_col",
            "field_type": "text",
            "initially_selected": True,
        }
    ]


@pytest.mark.django_db(transaction=True)
def test_postgresql_data_sync_table_connect_to_same_database(data_fixture):
    default_database = settings.DATABASES["default"]
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    with pytest.raises(SyncError) as e:
        with override_settings(
            BASEROW_PREVENT_POSTGRESQL_DATA_SYNC_CONNECTION_TO_DATABASE=True
        ):
            data_sync = handler.create_data_sync_table(
                user=user,
                database=database,
                table_name="Test",
                type_name="postgresql",
                synced_properties=["id"],
                postgresql_host=default_database["HOST"],
                postgresql_username=default_database["USER"],
                postgresql_password=default_database["PASSWORD"],
                postgresql_port=default_database["PORT"],
                postgresql_database=default_database["NAME"],
                postgresql_table="test_table",
                postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
            )
            handler.sync_data_sync_table(user=user, data_sync=data_sync)

    # This is expected to fail because `postgresql_host` is equal to the
    # default_database["HOST"] and that's not allowed if
    # BASEROW_PREVENT_POSTGRESQL_DATA_SYNC_CONNECTION_TO_DATABASE=True.
    assert str(e.value) == "It's not allowed to connect to this hostname."


@pytest.mark.django_db(transaction=True)
def test_postgresql_data_sync_table_connect_to_blacklist(data_fixture):
    default_database = settings.DATABASES["default"]
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    with pytest.raises(SyncError) as e:
        with override_settings(
            BASEROW_POSTGRESQL_DATA_SYNC_BLACKLIST=["localhost", "baserow.io"]
        ):
            data_sync = handler.create_data_sync_table(
                user=user,
                database=database,
                table_name="Test",
                type_name="postgresql",
                synced_properties=["id"],
                postgresql_host="localhost",
                postgresql_username=default_database["USER"],
                postgresql_password=default_database["PASSWORD"],
                postgresql_port=default_database["PORT"],
                postgresql_database=default_database["NAME"],
                postgresql_table="test_table",
                postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
            )
            handler.sync_data_sync_table(user=user, data_sync=data_sync)

    # This is expected to fail because `postgresql_host` is equal to the to one of the
    # hostnames in BASEROW_POSTGRESQL_DATA_SYNC_BLACKLIST.
    assert str(e.value) == "It's not allowed to connect to this hostname."


@pytest.mark.django_db(transaction=True)
def test_postgresql_data_sync_table_does_not_exist(data_fixture):
    default_database = settings.DATABASES["default"]
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    with pytest.raises(SyncError) as e:
        data_sync = handler.create_data_sync_table(
            user=user,
            database=database,
            table_name="Test",
            type_name="postgresql",
            synced_properties=["id"],
            postgresql_host=default_database["HOST"],
            postgresql_username=default_database["USER"],
            postgresql_password=default_database["PASSWORD"],
            postgresql_port=default_database["PORT"],
            postgresql_database=default_database["NAME"],
            postgresql_table="test_table_DOES_NOT_EXIST",
            postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
        )
        handler.sync_data_sync_table(user=user, data_sync=data_sync)

    assert str(e.value) == "The table test_table_DOES_NOT_EXIST does not exist."


@pytest.mark.django_db
def test_postgresql_data_sync_connection_error(data_fixture):
    default_database = settings.DATABASES["default"]
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    with pytest.raises(SyncError) as e:
        data_sync = handler.create_data_sync_table(
            user=user,
            database=database,
            table_name="Test",
            type_name="postgresql",
            synced_properties=["id"],
            postgresql_host=default_database["HOST"],
            postgresql_username="NOT_EXISTING_USER",
            postgresql_password=default_database["PASSWORD"],
            postgresql_port=default_database["PORT"],
            postgresql_database=default_database["NAME"],
            postgresql_table="test_table_DOES_NOT_EXIST",
            postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
        )
        handler.sync_data_sync_table(user=user, data_sync=data_sync)

    assert "failed" in str(e.value)


@pytest.mark.django_db(transaction=True)
def test_postgresql_data_sync_initial_table_limit(
    data_fixture, create_postgresql_test_table
):
    default_database = settings.DATABASES["default"]
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        synced_properties=["id"],
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=create_postgresql_test_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )

    with override_settings(INITIAL_TABLE_DATA_LIMIT=1):
        handler.sync_data_sync_table(user=user, data_sync=data_sync)

    assert data_sync.last_sync is None
    assert data_sync.last_error == "The table can't contain more than 1 records."


@pytest.mark.django_db(transaction=True)
def test_get_data_sync(data_fixture, api_client, create_postgresql_test_table):
    default_database = settings.DATABASES["default"]
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        synced_properties=["id"],
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=create_postgresql_test_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )

    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": data_sync.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert "postgresql_password" not in response_json


@pytest.mark.django_db(transaction=True)
def test_update_data_sync_table_changing_primary_key(
    data_fixture, create_postgresql_test_table
):
    default_database = settings.DATABASES["default"]
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        synced_properties=["id"],
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=create_postgresql_test_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )

    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            ALTER TABLE {create_postgresql_test_table}
            RENAME COLUMN id TO new_id;
        """
        )

    with transaction.atomic():
        handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 1
    assert fields[0].name == "new_id"
    assert fields[0].primary is True


@pytest.mark.django_db(transaction=True)
def test_update_data_sync_table_changing_primary_key_with_different_primary_field(
    data_fixture, create_postgresql_test_table
):
    default_database = settings.DATABASES["default"]
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        synced_properties=["id", "text_col"],
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=create_postgresql_test_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )

    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))

    with transaction.atomic():
        FieldHandler().change_primary_field(
            user=user, table=data_sync.table, new_primary_field=fields[1]
        )

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            ALTER TABLE {create_postgresql_test_table}
            RENAME COLUMN id TO new_id;
        """
        )

    with transaction.atomic():
        handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 2
    assert fields[0].name == "text_col"
    assert fields[0].primary is True
    assert fields[1].name == "new_id"
    assert fields[1].primary is False


@pytest.mark.django_db(transaction=True)
def test_update_data_sync_table_changing_table_with_different_primary_key(
    data_fixture, create_postgresql_test_table
):
    default_database = settings.DATABASES["default"]
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        synced_properties=["id", "text_col"],
        postgresql_host=default_database["HOST"],
        postgresql_username=default_database["USER"],
        postgresql_password=default_database["PASSWORD"],
        postgresql_port=default_database["PORT"],
        postgresql_database=default_database["NAME"],
        postgresql_table=create_postgresql_test_table,
        postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
    )

    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            CREATE TABLE {create_postgresql_test_table}_2 (
                car_id SERIAL PRIMARY KEY,
                make VARCHAR(50) NOT NULL,
                model VARCHAR(50) NOT NULL
            );
        """
        )
        cursor.execute(
            f"""
            INSERT INTO {create_postgresql_test_table}_2
                (make, model)
            VALUES
                ('make 1', 'model 2'),
                ('make 2', 'model 2'),
                ('make 3', 'model 3')
        """
        )

    with transaction.atomic():
        data_sync = handler.update_data_sync_table(
            user=user,
            data_sync=data_sync,
            synced_properties=["car_id"],
            postgresql_table=f"{create_postgresql_test_table}_2",
        )
        handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 1
    assert fields[0].name == "car_id"
    assert fields[0].primary is True

    model = data_sync.table.get_model()
    rows = model.objects.all()
    assert len(rows) == 3

    assert getattr(rows[0], f"field_{fields[0].id}") == Decimal("1")
    assert getattr(rows[1], f"field_{fields[0].id}") == Decimal("2")
    assert getattr(rows[2], f"field_{fields[0].id}") == Decimal("3")


@pytest.mark.django_db(transaction=True)
def test_create_data_sync_via_api_without_a_primary_property(
    data_fixture, api_client, create_postgresql_test_table
):
    default_database = settings.DATABASES["default"]
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            CREATE TABLE {create_postgresql_test_table}_3 (id integer)
            """
        )

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "postgresql",
            "synced_properties": ["id"],
            "postgresql_host": default_database["HOST"],
            "postgresql_username": default_database["USER"],
            "postgresql_password": default_database["PASSWORD"],
            "postgresql_port": default_database["PORT"],
            "postgresql_database": default_database["NAME"],
            "postgresql_table": create_postgresql_test_table + "_3",
            "postgresql_sslmode": default_database["OPTIONS"].get("sslmode", "prefer"),
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_UNIQUE_PRIMARY_PROPERTY_NOT_FOUND"


@pytest.mark.django_db(transaction=True)
def test_create_data_sync_with_negative_int_and_positive_baserow_number_field(
    data_fixture, api_client, create_postgresql_test_table
):
    default_database = settings.DATABASES["default"]
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "postgresql",
            "synced_properties": ["id", "int_col"],
            "postgresql_host": default_database["HOST"],
            "postgresql_username": default_database["USER"],
            "postgresql_password": default_database["PASSWORD"],
            "postgresql_port": default_database["PORT"],
            "postgresql_database": default_database["NAME"],
            "postgresql_table": create_postgresql_test_table,
            "postgresql_sslmode": default_database["OPTIONS"].get("sslmode", "prefer"),
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    data_sync_id = response.json()["data_sync"]["id"]

    data_sync = DataSync.objects.get(pk=data_sync_id)
    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 2

    FieldHandler().update_field(user=user, field=fields[1], number_negative=False)

    # Inserts a couple of random rows for testing purposes.
    insert_sql = f"""
    INSERT INTO {create_postgresql_test_table} (int_col)
    VALUES (%s)
    """

    with connection.cursor() as cursor:
        cursor.execute(
            insert_sql,
            (-10,),
        )

    transaction.commit()

    api_client.post(
        reverse(
            "api:database:data_sync:sync_table",
            kwargs={"data_sync_id": data_sync_id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    job = SyncDataSyncTableJob.objects.all().first()

    response = api_client.get(
        reverse(
            "api:jobs:item",
            kwargs={"job_id": job.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    job = response.json()
    assert job["state"] == "failed"
    assert job["type"] == "sync_data_sync_table"
    assert job["progress_percentage"] > 0
    assert job["data_sync"]["id"] == data_sync_id
    assert (
        job["human_readable_error"]
        == f"The value for field {fields[1].id} cannot be negative."
    )
