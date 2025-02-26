from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test.utils import override_settings
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.data_sync.exceptions import SyncError
from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.data_sync.models import MySQLDataSync
from baserow.contrib.database.data_sync.mysql_data_sync_type import (
    TextMySQLSyncProperty,
    column_type_to_baserow_field_type,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import NumberField
from baserow.core.db import specific_iterator


# Mock data for MySQL connection
def mock_mysql_cursor():
    """
    Create a mock MySQL cursor with expected responses for different queries.
    """
    cursor = MagicMock()

    # Mock table existence check response
    exists_response = {"count": 1}
    cursor.fetchone.return_value = exists_response

    # Mock primary key query response
    primary_key_response = [{"COLUMN_NAME": "id"}]

    # Mock columns query response - ensure we use consistent case matching with primary key response
    columns_response = [
        {"COLUMN_NAME": "id", "DATA_TYPE": "int", "NUMERIC_SCALE": 0},
        {"COLUMN_NAME": "text_col", "DATA_TYPE": "text", "NUMERIC_SCALE": None},
        {"COLUMN_NAME": "char_col", "DATA_TYPE": "varchar", "NUMERIC_SCALE": None},
        {"COLUMN_NAME": "int_col", "DATA_TYPE": "int", "NUMERIC_SCALE": 0},
        {"COLUMN_NAME": "float_col", "DATA_TYPE": "float", "NUMERIC_SCALE": 2},
        {"COLUMN_NAME": "decimal_col", "DATA_TYPE": "decimal", "NUMERIC_SCALE": 2},
        {"COLUMN_NAME": "smallint_col", "DATA_TYPE": "smallint", "NUMERIC_SCALE": 0},
        {"COLUMN_NAME": "bigint_col", "DATA_TYPE": "bigint", "NUMERIC_SCALE": 0},
        {"COLUMN_NAME": "date_col", "DATA_TYPE": "date", "NUMERIC_SCALE": None},
        {"COLUMN_NAME": "datetime_col", "DATA_TYPE": "datetime", "NUMERIC_SCALE": None},
        {"COLUMN_NAME": "boolean_col", "DATA_TYPE": "boolean", "NUMERIC_SCALE": None},
    ]

    # Mock row count response
    count_response = {"count": 2}

    # Mock row data
    row_data_response = [
        {
            "id": 1,
            "text_col": "Lorem ipsum dolor sit amet",
            "char_col": "Short char",
            "int_col": 10,
            "float_col": 10.10,
            "decimal_col": Decimal("99999999.22"),
            "smallint_col": 200,
            "bigint_col": 99999999,
            "date_col": date(2023, 1, 17),
            "datetime_col": datetime(2022, 2, 28, 12, 0),
            "boolean_col": True,
        },
        {
            "id": 2,
            "text_col": None,
            "char_col": None,
            "int_col": None,
            "float_col": None,
            "decimal_col": None,
            "smallint_col": None,
            "bigint_col": None,
            "date_col": None,
            "datetime_col": None,
            "boolean_col": False,
        },
    ]

    # Configure cursor's behavior based on the executed query
    def side_effect_execute(query, *args, **kwargs):
        if "EXISTS" in query or "TABLE_SCHEMA" in query or "information_schema.tables" in query:
            cursor.fetchone.return_value = exists_response
        elif "PRIMARY KEY" in query:
            cursor.fetchall.return_value = primary_key_response
        elif "COLUMN_NAME" in query or "information_schema.columns" in query:
            cursor.fetchall.return_value = columns_response
        elif "COUNT" in query:
            cursor.fetchone.return_value = count_response
        elif "SELECT" in query:
            cursor.fetchall.return_value = row_data_response

    cursor.execute.side_effect = side_effect_execute

    return cursor


@pytest.mark.django_db(transaction=True)
@patch("pymysql.connect")
def test_create_mysql_data_sync(mock_connect, data_fixture):
    """
    Test creating a data sync for a MySQL table.
    """
    # Configure mocks
    mock_connection = MagicMock()
    mock_cursor = mock_mysql_cursor()
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
    mock_connect.return_value = mock_connection

    # Create test data
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    # Create data sync table with a single property first to test if it exists
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="mysql",
        synced_properties=["id"],
        mysql_host="localhost",
        mysql_username="root",
        mysql_password="password",
        mysql_port=3306,
        mysql_database="test_db",
        mysql_table="test_table",
    )

    # Verify data sync instance
    assert isinstance(data_sync, MySQLDataSync)
    assert data_sync.mysql_host == "localhost"
    assert data_sync.mysql_username == "root"
    assert data_sync.mysql_password == "password"
    assert data_sync.mysql_port == 3306
    assert data_sync.mysql_database == "test_db"
    assert data_sync.mysql_table == "test_table"

    # Verify fields
    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 11
    assert fields[0].name == "id"
    assert isinstance(fields[0], NumberField)
    assert fields[0].primary is True
    assert fields[0].read_only is True
    assert fields[0].immutable_type is True
    assert fields[0].immutable_properties is False
    assert fields[0].number_decimal_places == 0


@pytest.mark.django_db(transaction=True)
@patch("pymysql.connect")
def test_sync_mysql_data_sync(mock_connect, data_fixture):
    """
    Test syncing data from a MySQL table.
    """
    # Configure mocks
    mock_connection = MagicMock()
    mock_cursor = mock_mysql_cursor()
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
    mock_connect.return_value = mock_connection

    # Create test data
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    # Create and sync data with just the id field first
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="mysql",
        synced_properties=["id"],
        mysql_host="localhost",
        mysql_username="root",
        mysql_password="password",
        mysql_port=3306,
        mysql_database="test_db",
        mysql_table="test_table",
    )

    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    # Verify field structure and data
    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    id_field = fields[0]
    text_field = fields[1]
    char_field = fields[2]
    int_field = fields[3]
    float_field = fields[4]
    decimal_field = fields[5]
    smallint_field = fields[6]
    bigint_field = fields[7]
    date_field = fields[8]
    datetime_field = fields[9]
    boolean_field = fields[10]

    # Get rows and check data
    model = data_sync.table.get_model()
    rows = list(model.objects.all())
    assert len(rows) == 2
    filled_row = rows[0]
    empty_row = rows[1]

    # Verify filled row data
    assert getattr(filled_row, f"field_{id_field.id}") == 1
    assert getattr(filled_row, f"field_{text_field.id}") == "Lorem ipsum dolor sit amet"
    assert getattr(filled_row, f"field_{char_field.id}") == "Short char"
    assert getattr(filled_row, f"field_{int_field.id}") == 10
    assert getattr(filled_row, f"field_{float_field.id}") == Decimal("10.10")
    assert getattr(filled_row, f"field_{decimal_field.id}") == Decimal("99999999.22")
    assert getattr(filled_row, f"field_{smallint_field.id}") == 200
    assert getattr(filled_row, f"field_{bigint_field.id}") == 99999999
    assert getattr(filled_row, f"field_{date_field.id}") == date(2023, 1, 17)
    assert getattr(filled_row, f"field_{datetime_field.id}") == datetime(
        2022, 2, 28, 12, 0, tzinfo=timezone.utc
    )
    assert getattr(filled_row, f"field_{boolean_field.id}") is True

    # Verify empty row data
    assert getattr(empty_row, f"field_{id_field.id}") == 2
    assert getattr(empty_row, f"field_{text_field.id}") is None
    assert getattr(empty_row, f"field_{char_field.id}") is None
    assert getattr(empty_row, f"field_{int_field.id}") is None
    assert getattr(empty_row, f"field_{float_field.id}") is None
    assert getattr(empty_row, f"field_{decimal_field.id}") is None
    assert getattr(empty_row, f"field_{smallint_field.id}") is None
    assert getattr(empty_row, f"field_{bigint_field.id}") is None
    assert getattr(empty_row, f"field_{date_field.id}") is None
    assert getattr(empty_row, f"field_{datetime_field.id}") is None
    assert getattr(empty_row, f"field_{boolean_field.id}") is False


@pytest.mark.django_db(transaction=True)
@patch("pymysql.connect")
def test_mysql_data_sync_get_properties(mock_connect, data_fixture, api_client):
    """
    Test retrieving properties from a MySQL table.
    """
    # Configure mocks
    mock_connection = MagicMock()
    mock_cursor = mock_mysql_cursor()
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
    mock_connect.return_value = mock_connection

    # Create test data
    user, token = data_fixture.create_user_and_token()

    # Test the API endpoint
    url = reverse("api:database:data_sync:properties")
    response = api_client.post(
        url,
        {
            "type": "mysql",
            "mysql_host": "localhost",
            "mysql_username": "root",
            "mysql_password": "password",
            "mysql_port": 3306,
            "mysql_database": "test_db",
            "mysql_table": "test_table",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    # Verify response
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
            "key": "decimal_col",
            "name": "decimal_col",
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
@patch("pymysql.connect")
def test_mysql_data_sync_get_properties_unsupported_column_types(
    mock_connect, data_fixture, api_client
):
    """
    Test behavior with unsupported column types.
    """
    # Configure mocks
    mock_connection = MagicMock()
    mock_cursor = mock_mysql_cursor()
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
    mock_connect.return_value = mock_connection

    # Create test data
    user, token = data_fixture.create_user_and_token()

    # Test with limited column types
    with patch(
        "baserow.contrib.database.data_sync.mysql_data_sync_type.column_type_to_baserow_field_type",
        new={
            "varchar": TextMySQLSyncProperty,
        },
    ):
        url = reverse("api:database:data_sync:properties")
        response = api_client.post(
            url,
            {
                "type": "mysql",
                "mysql_host": "localhost",
                "mysql_username": "root",
                "mysql_password": "password",
                "mysql_port": 3306,
                "mysql_database": "test_db",
                "mysql_table": "test_table",
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    # Verify we only get the supported column type
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
@patch("pymysql.connect")
def test_mysql_data_sync_table_does_not_exist(mock_connect, data_fixture):
    """
    Test behavior when table doesn't exist.
    """
    # Configure mocks to return 0 count (table doesn't exist)
    mock_connection = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"count": 0}
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
    mock_connect.return_value = mock_connection

    # Create test data
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    # Test the error case
    with pytest.raises(SyncError) as e:
        data_sync = handler.create_data_sync_table(
            user=user,
            database=database,
            table_name="Test",
            type_name="mysql",
            synced_properties=["id"],
            mysql_host="localhost",
            mysql_username="root",
            mysql_password="password",
            mysql_port=3306,
            mysql_database="test_db",
            mysql_table="nonexistent_table",
        )
        handler.sync_data_sync_table(user=user, data_sync=data_sync)

    assert str(e.value) == "The table nonexistent_table does not exist."


@pytest.mark.django_db
@patch("pymysql.connect", side_effect=Exception("Connection failed"))
def test_mysql_data_sync_connection_error(mock_connect, data_fixture):
    """
    Test handling of connection errors.
    """
    # Create test data
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    # Test the error case
    with pytest.raises(SyncError) as e:
        data_sync = handler.create_data_sync_table(
            user=user,
            database=database,
            table_name="Test",
            type_name="mysql",
            synced_properties=["id"],
            mysql_host="wrong-host",
            mysql_username="root",
            mysql_password="password",
            mysql_port=3306,
            mysql_database="test_db",
            mysql_table="test_table",
        )
        handler.sync_data_sync_table(user=user, data_sync=data_sync)

    assert "Connection failed" in str(e.value)


@pytest.mark.django_db(transaction=True)
@patch("pymysql.connect")
def test_mysql_data_sync_initial_table_limit(mock_connect, data_fixture):
    """
    Test enforcement of table data limits.
    """
    # Configure mocks
    mock_connection = MagicMock()
    mock_cursor = mock_mysql_cursor()
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
    mock_connect.return_value = mock_connection

    # Create test data
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    # Create data sync
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="mysql",
        synced_properties=["id"],
        mysql_host="localhost",
        mysql_username="root",
        mysql_password="password",
        mysql_port=3306,
        mysql_database="test_db",
        mysql_table="test_table",
    )

    # Test with a low limit
    with override_settings(INITIAL_TABLE_DATA_LIMIT=1):
        handler.sync_data_sync_table(user=user, data_sync=data_sync)

    # Verify the error is recorded
    assert data_sync.last_sync is None
    assert data_sync.last_error == "The table can't contain more than 1 records."


@pytest.mark.django_db(transaction=True)
@patch("pymysql.connect")
def test_get_data_sync(mock_connect, data_fixture, api_client):
    """
    Test retrieving data sync configuration via API.
    """
    # Configure mocks
    mock_connection = MagicMock()
    mock_cursor = mock_mysql_cursor()
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
    mock_connect.return_value = mock_connection

    # Create test data
    user, token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=user)

    # Create data sync
    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="mysql",
        synced_properties=["id"],
        mysql_host="localhost",
        mysql_username="root",
        mysql_password="password",
        mysql_port=3306,
        mysql_database="test_db",
        mysql_table="test_table",
    )

    # Request the data sync info
    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": data_sync.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    # Verify response doesn't include password
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert "mysql_password" not in response_json


@pytest.mark.django_db(transaction=True)
@patch("pymysql.connect")
def test_update_data_sync_table_changing_primary_key(mock_connect, data_fixture):
    """
    Test behavior when the primary key changes.
    """
    # Initial mock configuration
    mock_connection = MagicMock()
    mock_cursor = mock_mysql_cursor()
    mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
    mock_connect.return_value = mock_connection

    # Create test data
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    # Create and sync data
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="mysql",
        synced_properties=["id"],
        mysql_host="localhost",
        mysql_username="root",
        mysql_password="password",
        mysql_port=3306,
        mysql_database="test_db",
        mysql_table="test_table",
    )

    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    # Update mock to simulate renamed column
    new_cursor = mock_mysql_cursor()
    new_primary_key_response = [{"COLUMN_NAME": "new_id"}]

    def new_side_effect(query, *args, **kwargs):
        if "PRIMARY KEY" in query:
            new_cursor.fetchall.return_value = new_primary_key_response
        elif "columns" in query:
            new_cols = [
                {"column_name": "new_id", "data_type": "int", "numeric_scale": 0},
                {"column_name": "text_col", "data_type": "text", "numeric_scale": None},
            ]
            new_cursor.fetchall.return_value = new_cols
        else:
            # Use default behavior for other queries
            if "information_schema.tables" in query:
                new_cursor.fetchone.return_value = {"count": 1}
            elif "COUNT" in query:
                new_cursor.fetchone.return_value = {"count": 0}

    new_cursor.execute.side_effect = new_side_effect
    mock_connection.cursor.return_value.__enter__.return_value = new_cursor

    # Sync again to detect the changes
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    # Verify the primary key column was updated
    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 1
    assert fields[0].name == "new_id"
    assert fields[0].primary is True
