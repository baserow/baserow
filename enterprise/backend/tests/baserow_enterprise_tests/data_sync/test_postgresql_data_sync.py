from datetime import date, datetime, timezone
from decimal import Decimal

from django.conf import settings
from django.db import connection, transaction
from django.test.utils import override_settings

import pytest
from celery.app.task import Task

from baserow.contrib.database.api.rows.serializers import serialize_rows_for_response
from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.registries import (
    data_sync_type_registry,
    two_way_sync_strategy_type_registry,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.db import specific_iterator


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_create_row_in_postgresql_table(
    enterprise_data_fixture, create_postgresql_test_table, synced_roles
):
    enterprise_data_fixture.enable_enterprise()
    default_database = settings.DATABASES["default"]
    user = enterprise_data_fixture.create_user()

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        two_way_sync=True,
        synced_properties=[
            "id",
            "text_col",
            "int_col",
            "numeric_col",
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

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    id_field = fields[0]
    text_field = fields[1]
    int_field = fields[2]
    numeric_field = fields[3]
    decimal_field = fields[4]
    date_field = fields[5]
    datetime_field = fields[6]
    boolean_field = fields[7]

    row_handler = RowHandler()
    rows = row_handler.create_rows(
        user=user,
        table=data_sync.table,
        rows_values=[
            {
                f"field_{text_field.id}": "text",
                f"field_{int_field.id}": 1,
                f"field_{numeric_field.id}": "1",
                f"field_{decimal_field.id}": "1",
                f"field_{date_field.id}": "2021-01-01",
                f"field_{datetime_field.id}": "2021-01-01 12:00",
                f"field_{boolean_field.id}": True,
            }
        ],
        signal_params={"skip_two_way_sync": True},
    ).created_rows

    model = data_sync.table.get_model()
    serialized_rows = serialize_rows_for_response(rows, model)
    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    two_way_sync_strategy = two_way_sync_strategy_type_registry.get(
        data_sync_type.two_way_sync_strategy_type
    )

    two_way_sync_strategy.rows_created(Task(), serialized_rows, data_sync)

    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT id, text_col, int_col, numeric_col, decimal_col, date_col, datetime_col, boolean_col "
            f"FROM {create_postgresql_test_table} ORDER BY id DESC LIMIT 1"
        )
        result = cursor.fetchone()
        assert result is not None
        fetched_id = result[0]
        assert result[1] == "text"
        assert result[2] == 1
        assert result[3] == Decimal("1")
        assert result[4] == Decimal("1")
        assert result[5] == date(2021, 1, 1)
        assert result[6].replace(tzinfo=timezone.utc) == datetime(
            2021, 1, 1, 12, 0, tzinfo=timezone.utc
        )
        assert result[7] is True

    rows[0].refresh_from_db()
    postgres_id = getattr(rows[0], f"field_{id_field.id}")
    assert postgres_id == fetched_id


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_update_row_in_postgresql_table(
    enterprise_data_fixture,
    create_postgresql_test_table,
    synced_roles,
):
    enterprise_data_fixture.enable_enterprise()
    default_database = settings.DATABASES["default"]
    user = enterprise_data_fixture.create_user()

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        two_way_sync=True,
        synced_properties=[
            "id",
            "text_col",
            "int_col",
            "numeric_col",
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
    int_field = fields[2]
    numeric_field = fields[3]
    decimal_field = fields[4]
    date_field = fields[5]
    datetime_field = fields[6]
    boolean_field = fields[7]

    model = data_sync.table.get_model()
    rows = model.objects.all()

    row_handler = RowHandler()

    with transaction.atomic():
        rows = row_handler.update_rows(
            user=user,
            table=data_sync.table,
            rows_values=[
                {
                    "id": rows[0].id,
                    f"field_{text_field.id}": "text",
                    f"field_{int_field.id}": 1,
                    f"field_{numeric_field.id}": "1",
                    f"field_{decimal_field.id}": "1",
                    f"field_{date_field.id}": "2021-01-01",
                    f"field_{datetime_field.id}": "2021-01-01 12:00",
                    f"field_{boolean_field.id}": True,
                }
            ],
            signal_params={"skip_two_way_sync": True},
        )[0]

    serialized_rows = serialize_rows_for_response(rows, model)
    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    two_way_sync_strategy = two_way_sync_strategy_type_registry.get(
        data_sync_type.two_way_sync_strategy_type
    )

    two_way_sync_strategy.rows_updated(
        Task(),
        serialized_rows,
        data_sync,
        updated_field_ids=[
            text_field.id,
            int_field.id,
            numeric_field.id,
            decimal_field.id,
            date_field.id,
            datetime_field.id,
            boolean_field.id,
        ],
    )

    with connection.cursor() as cursor:
        row_id = getattr(rows[0], f"field_{id_field.id}")
        cursor.execute(
            f"SELECT id, text_col, int_col, numeric_col, decimal_col, date_col, datetime_col, boolean_col "
            f"FROM {create_postgresql_test_table} WHERE id = {row_id} LIMIT 1"
        )
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == row_id
        assert result[1] == "text"
        assert result[2] == 1
        assert result[3] == Decimal("1")
        assert result[4] == Decimal("1")
        assert result[5] == date(2021, 1, 1)
        assert result[6].replace(tzinfo=timezone.utc) == datetime(
            2021, 1, 1, 12, 0, tzinfo=timezone.utc
        )
        assert result[7] is True


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_update_row_in_postgresql_table_with_multiple_primary_keys(
    enterprise_data_fixture,
    create_postgresql_test_table,
    synced_roles,
):
    enterprise_data_fixture.enable_enterprise()
    default_database = settings.DATABASES["default"]
    user = enterprise_data_fixture.create_user()

    table_name = "test_table_multi_pk"
    create_table_sql = f"""
    CREATE TABLE {table_name} (
        id INTEGER NOT NULL,
        pk2 TEXT NOT NULL,
        text_col TEXT,
        PRIMARY KEY (id, pk2)
    )
    """
    insert_sql = f"""
    INSERT INTO {table_name} (id, pk2, text_col)
    VALUES (%s, %s, %s)
    """

    with connection.cursor() as cursor:
        cursor.execute(create_table_sql)
        cursor.execute(insert_sql, (1, "A", "original"))
    transaction.commit()

    try:
        database = enterprise_data_fixture.create_database_application(user=user)
        handler = DataSyncHandler()

        data_sync = handler.create_data_sync_table(
            user=user,
            database=database,
            table_name="Test",
            type_name="postgresql",
            two_way_sync=True,
            synced_properties=[
                "id",
                "pk2",
                "text_col",
            ],
            postgresql_host=default_database["HOST"],
            postgresql_username=default_database["USER"],
            postgresql_password=default_database["PASSWORD"],
            postgresql_port=default_database["PORT"],
            postgresql_database=default_database["NAME"],
            postgresql_table=table_name,
            postgresql_sslmode=default_database["OPTIONS"].get("sslmode", "prefer"),
        )

        handler.sync_data_sync_table(user=user, data_sync=data_sync)

        fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
        id_field = fields[0]
        pk2_field = fields[1]
        text_field = fields[2]

        model = data_sync.table.get_model()
        rows = model.objects.all()

        row_handler = RowHandler()

        with transaction.atomic():
            rows = row_handler.update_rows(
                user=user,
                table=data_sync.table,
                rows_values=[
                    {
                        "id": rows[0].id,
                        f"field_{text_field.id}": "updated",
                    }
                ],
                signal_params={"skip_two_way_sync": True},
            )[0]

        serialized_rows = serialize_rows_for_response(rows, model)
        data_sync_type = data_sync_type_registry.get_by_model(data_sync)
        two_way_sync_strategy = two_way_sync_strategy_type_registry.get(
            data_sync_type.two_way_sync_strategy_type
        )

        two_way_sync_strategy.rows_updated(
            Task(),
            serialized_rows,
            data_sync,
            updated_field_ids=[text_field.id],
        )

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT id, pk2, text_col
                FROM {table_name}
                ORDER BY id
                """
            )
            results = cursor.fetchall()
            assert results[0][2] == "updated"

    finally:
        # Clean up dynamically created table
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        transaction.commit()


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_skip_update_row_in_postgresql_table_if_unique_primary_is_empty(
    enterprise_data_fixture,
    create_postgresql_test_table,
    synced_roles,
):
    enterprise_data_fixture.enable_enterprise()
    default_database = settings.DATABASES["default"]
    user = enterprise_data_fixture.create_user()

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        two_way_sync=True,
        synced_properties=[
            "id",
            "text_col",
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

    model = data_sync.table.get_model()
    rows = list(model.objects.all())
    old_id = getattr(rows[0], f"field_{id_field.id}")
    setattr(rows[0], f"field_{id_field.id}", None)
    rows[0].save()

    row_handler = RowHandler()

    with transaction.atomic():
        rows = row_handler.update_rows(
            user=user,
            table=data_sync.table,
            rows_values=[
                {
                    "id": rows[0].id,
                    f"field_{text_field.id}": "new",
                }
            ],
            signal_params={"skip_two_way_sync": True},
        )[0]

    serialized_rows = serialize_rows_for_response(rows, model)
    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    two_way_sync_strategy = two_way_sync_strategy_type_registry.get(
        data_sync_type.two_way_sync_strategy_type
    )

    two_way_sync_strategy.rows_updated(
        Task(),
        serialized_rows,
        data_sync,
        updated_field_ids=[text_field.id],
    )

    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT id, text_col "
            f"FROM {create_postgresql_test_table} WHERE id = {old_id} LIMIT 1"
        )
        result = cursor.fetchone()
        assert result is not None
        # Should still  have the old value because the unique primary is empty, and
        # it's therefore not allowed to do the update on the row.
        assert result[1] == (
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Maecenas non "
            "nunc et sapien ultricies blandit. "
        )


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_delete_row_in_postgresql_table(
    enterprise_data_fixture,
    create_postgresql_test_table,
    synced_roles,
):
    enterprise_data_fixture.enable_enterprise()
    default_database = settings.DATABASES["default"]
    user = enterprise_data_fixture.create_user()

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        two_way_sync=True,
        synced_properties=[
            "id",
            "text_col",
            "int_col",
            "numeric_col",
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

    model = data_sync.table.get_model()
    rows = model.objects.all()
    serialized_rows = serialize_rows_for_response([rows[0]], model)

    row_handler = RowHandler()

    with transaction.atomic():
        row_handler.delete_rows(
            user=user,
            table=data_sync.table,
            row_ids=[rows[0].id],
            signal_params={"skip_two_way_sync": True},
        )

    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    two_way_sync_strategy = two_way_sync_strategy_type_registry.get(
        data_sync_type.two_way_sync_strategy_type
    )

    two_way_sync_strategy.rows_deleted(Task(), serialized_rows, data_sync)

    with connection.cursor() as cursor:
        row_id = serialized_rows[0][f"field_{id_field.id}"]
        cursor.execute(
            f"SELECT count(*) " f"FROM {create_postgresql_test_table} WHERE id = %s",
            [row_id],
        )
        result = cursor.fetchone()
        assert result[0] == 0


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_skip_delete_row_in_postgresql_table_if_unique_primary_is_empty(
    enterprise_data_fixture,
    create_postgresql_test_table,
    synced_roles,
):
    enterprise_data_fixture.enable_enterprise()
    default_database = settings.DATABASES["default"]
    user = enterprise_data_fixture.create_user()

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="postgresql",
        two_way_sync=True,
        synced_properties=[
            "id",
            "text_col",
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

    model = data_sync.table.get_model()
    rows = list(model.objects.all())
    old_id = getattr(rows[0], f"field_{id_field.id}")
    setattr(rows[0], f"field_{id_field.id}", None)
    rows[0].save()

    serialized_rows = serialize_rows_for_response([rows[0]], model)

    row_handler = RowHandler()

    with transaction.atomic():
        row_handler.delete_rows(
            user=user,
            table=data_sync.table,
            row_ids=[rows[0].id],
            signal_params={"skip_two_way_sync": True},
        )

    data_sync_type = data_sync_type_registry.get_by_model(data_sync)
    two_way_sync_strategy = two_way_sync_strategy_type_registry.get(
        data_sync_type.two_way_sync_strategy_type
    )

    two_way_sync_strategy.rows_deleted(Task(), serialized_rows, data_sync)

    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT count(*) " f"FROM {create_postgresql_test_table} WHERE id = %s",
            [old_id],
        )
        result = cursor.fetchone()
        assert result[0] == 1
