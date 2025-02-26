import contextlib
from typing import Any, Dict, List, Optional

from django.conf import settings

import pymysql
from pymysql import cursors

from baserow.contrib.database.fields.models import (
    NUMBER_MAX_DECIMAL_PLACES,
    BooleanField,
    DateField,
    LongTextField,
    NumberField,
    TextField,
)
from baserow.core.utils import ChildProgressBuilder

from .exceptions import SyncError
from .models import MySQLDataSync
from .registries import DataSyncProperty, DataSyncType
from .utils import compare_date


class BaseMySQLSyncProperty(DataSyncProperty):
    decimal_places = None

    def prepare_value(self, value):
        return value


class TextMySQLSyncProperty(BaseMySQLSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class LongTextMySQLSyncProperty(BaseMySQLSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> LongTextField:
        return LongTextField(name=self.name)


class BooleanMySQLSyncProperty(BaseMySQLSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> BooleanField:
        return BooleanField(name=self.name)

    def prepare_value(self, value):
        return bool(value)


class NumberMySQLSyncProperty(BaseMySQLSyncProperty):
    immutable_properties = False
    decimal_places = 0

    def __init__(self, key, name):
        super().__init__(key, name)

    def is_equal(self, baserow_row_value: Any, data_sync_row_value: Any) -> bool:
        try:
            return round(baserow_row_value, self.decimal_places) == round(
                data_sync_row_value, self.decimal_places
            )
        except TypeError:
            return super().is_equal(baserow_row_value, data_sync_row_value)

    def to_baserow_field(self) -> NumberField:
        return NumberField(
            name=self.name,
            number_decimal_places=min(
                self.decimal_places or 0, NUMBER_MAX_DECIMAL_PLACES
            ),
            number_negative=True,
        )


class DateMySQLSyncProperty(BaseMySQLSyncProperty):
    immutable_properties = False
    include_time = False

    def is_equal(self, baserow_row_value, data_sync_row_value) -> bool:
        return compare_date(baserow_row_value, data_sync_row_value)

    def to_baserow_field(self) -> DateField:
        return DateField(
            name=self.name,
            date_format="ISO",
            date_include_time=self.include_time,
            date_time_format="24",
            date_show_tzinfo=True,
        )


class DateTimeMySQLSyncProperty(DateMySQLSyncProperty):
    include_time = True


# Mapping MySQL column types to Baserow field types
column_type_to_baserow_field_type = {
    "int": NumberMySQLSyncProperty,
    "tinyint": NumberMySQLSyncProperty,
    "smallint": NumberMySQLSyncProperty,
    "mediumint": NumberMySQLSyncProperty,
    "bigint": NumberMySQLSyncProperty,
    "float": NumberMySQLSyncProperty,
    "double": NumberMySQLSyncProperty,
    "decimal": NumberMySQLSyncProperty,
    "bool": BooleanMySQLSyncProperty,
    "boolean": BooleanMySQLSyncProperty,
    "char": TextMySQLSyncProperty,
    "varchar": TextMySQLSyncProperty,
    "text": LongTextMySQLSyncProperty,
    "mediumtext": LongTextMySQLSyncProperty,
    "longtext": LongTextMySQLSyncProperty,
    "date": DateMySQLSyncProperty,
    "datetime": DateTimeMySQLSyncProperty,
    "timestamp": DateTimeMySQLSyncProperty,
}


class MySQLDataSyncType(DataSyncType):
    type = "mysql"
    model_class = MySQLDataSync
    allowed_fields = [
        "mysql_host",
        "mysql_username",
        "mysql_password",
        "mysql_port",
        "mysql_database",
        "mysql_table",
    ]
    request_serializer_field_names = [
        "mysql_host",
        "mysql_username",
        "mysql_password",
        "mysql_port",
        "mysql_database",
        "mysql_table",
    ]
    # The `mysql_password` should not be included because it's a secret value that
    # must only be possible to set and not get.
    serializer_field_names = [
        "mysql_host",
        "mysql_username",
        "mysql_port",
        "mysql_database",
        "mysql_table",
    ]

    @contextlib.contextmanager
    def _connection(self, instance):
        cursor = None
        connection = None

        try:
            connection = pymysql.connect(
                host=instance.mysql_host,
                port=instance.mysql_port,
                user=instance.mysql_username,
                password=instance.mysql_password,
                database=instance.mysql_database,
                cursorclass=cursors.DictCursor,
            )
            cursor = connection.cursor()
            yield cursor
        except pymysql.Error as e:
            raise SyncError(str(e))
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def _get_table_columns(self, instance):
        with self._connection(instance) as cursor:
            # Check if table exists
            exists_query = """
                SELECT COUNT(*) as count 
                FROM information_schema.tables 
                WHERE TABLE_SCHEMA = %s
                AND TABLE_NAME = %s
            """
            cursor.execute(
                exists_query, (instance.mysql_database, instance.mysql_table)
            )
            result = cursor.fetchone()
            count = result.get("count", 0)
            if count == 0:
                raise SyncError(f"The table {instance.mysql_table} does not exist.")

            # Get primary key columns
            primary_query = """
                SELECT k.COLUMN_NAME
                FROM information_schema.table_constraints t
                JOIN information_schema.key_column_usage k
                USING(constraint_name,table_schema,table_name)
                WHERE t.constraint_type='PRIMARY KEY'
                AND t.table_schema=%s
                AND t.table_name=%s
            """
            cursor.execute(
                primary_query, (instance.mysql_database, instance.mysql_table)
            )
            primary_columns = []
            for row in cursor.fetchall():
                column_name = row.get("COLUMN_NAME") or row.get("column_name")
                if column_name:
                    primary_columns.append(column_name)

            # Get all columns with their data types
            columns_query = """
                SELECT COLUMN_NAME, DATA_TYPE, NUMERIC_SCALE
                FROM information_schema.columns
                WHERE TABLE_SCHEMA = %s
                AND TABLE_NAME = %s
            """
            cursor.execute(
                columns_query, (instance.mysql_database, instance.mysql_table)
            )
            
            # Try to get columns with either uppercase or lowercase column names to handle
            # different MySQL server implementations and test mocks
            columns = []
            for row in cursor.fetchall():
                column_name = row.get("COLUMN_NAME") or row.get("column_name")
                data_type = row.get("DATA_TYPE") or row.get("data_type")
                numeric_scale = row.get("NUMERIC_SCALE") or row.get("numeric_scale")
                
                columns.append((column_name, data_type, numeric_scale))
            

        return primary_columns, columns

    def get_properties(self, instance) -> List[DataSyncProperty]:
        primary_columns, columns = self._get_table_columns(instance)
        properties = []
        for column_name, column_type, decimal_places in columns:
            is_primary = column_name in primary_columns
            property_class = None
            
            # Find matching field type
            for key, cls in column_type_to_baserow_field_type.items():
                if key.lower() in column_type.lower():
                    property_class = cls
                    break

            if property_class is None:
                continue

            property_instance = property_class(column_name, column_name)
            property_instance.unique_primary = is_primary
            property_instance.decimal_places = decimal_places or 0
            properties.append(property_instance)
        return properties

    def get_all_rows(
        self,
        instance,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> List[Dict]:
        table_name = instance.mysql_table
        properties = self.get_properties(instance)
        column_names = [p.key for p in properties]
        order_names = [p.key for p in properties if p.unique_primary]

        with self._connection(instance) as cursor:
            # Get row count first
            count_query = "SELECT COUNT(*) as count FROM `%s`"
            cursor.execute(count_query % cursor.connection.escape_string(table_name))
            result = cursor.fetchone()
            count = result.get("count", 0)

            limit = getattr(settings, "INITIAL_TABLE_DATA_LIMIT", None)
            if limit and count > limit:
                raise SyncError(f"The table can't contain more than {limit} records.")

            # Build the query with parameters to prevent SQL injection
            select_fields = ", ".join([f"`{name}`" for name in column_names])
            
            # Use parameter placeholders for proper escaping
            query = f"SELECT {select_fields} FROM `%s`"

            # Add ordering if primary keys exist
            if order_names:
                order_clause = ", ".join([f"`{name}`" for name in order_names])
                query += f" ORDER BY {order_clause}"

            # Execute with proper table name escaping
            cursor.execute(query % cursor.connection.escape_string(table_name))
            records = cursor.fetchall()

        # Convert from dict records to the expected format
        result = []
        for record in records:
            row_data = {}
            for p in properties:
                if p.key in record:
                    row_data[p.key] = p.prepare_value(record[p.key])
            result.append(row_data)

        return result
