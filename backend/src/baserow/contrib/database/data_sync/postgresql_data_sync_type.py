import contextlib
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db import DEFAULT_DB_ALIAS

from baserow.contrib.database.fields.models import (
    NUMBER_MAX_DECIMAL_PLACES,
    BooleanField,
    DateField,
    LongTextField,
    NumberField,
    TextField,
)
from baserow.core.psycopg import psycopg, sql
from baserow.core.utils import ChildProgressBuilder, are_hostnames_same

from .exceptions import SyncError
from .models import PostgreSQLDataSync
from .registries import DataSyncProperty, DataSyncType
from .utils import compare_date


class BasePostgreSQLSyncProperty(DataSyncProperty):
    decimal_places = None

    def prepare_value(self, value):
        return value


class TextPostgreSQLSyncProperty(BasePostgreSQLSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class LongTextPostgreSQLSyncProperty(BasePostgreSQLSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> LongTextField:
        return LongTextField(name=self.name)


class BooleanPostgreSQLSyncProperty(BasePostgreSQLSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> BooleanField:
        return BooleanField(name=self.name)

    def prepare_value(self, value):
        return bool(value)


class NumberPostgreSQLSyncProperty(BasePostgreSQLSyncProperty):
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


class DatePostgreSQLSyncProperty(BasePostgreSQLSyncProperty):
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


class DateTimePostgreSQLSyncProperty(DatePostgreSQLSyncProperty):
    include_time = True


# The key of the mapping must be in the column type to map to it. `integer` column
# type would therefore map to `NumberPostgreSQLSyncProperty`.
column_type_to_baserow_field_type = {
    "int": NumberPostgreSQLSyncProperty,
    "serial": NumberPostgreSQLSyncProperty,
    "boolean": BooleanPostgreSQLSyncProperty,
    "real": NumberPostgreSQLSyncProperty,
    "double": NumberPostgreSQLSyncProperty,
    "numeric": NumberPostgreSQLSyncProperty,
    "char": TextPostgreSQLSyncProperty,
    "text": LongTextPostgreSQLSyncProperty,
    "date": DatePostgreSQLSyncProperty,
    "timestamp": DateTimePostgreSQLSyncProperty,
    "uuid": TextPostgreSQLSyncProperty,
}


class PostgreSQLDataSyncType(DataSyncType):
    type = "postgresql"
    model_class = PostgreSQLDataSync
    allowed_fields = [
        "postgresql_host",
        "postgresql_username",
        "postgresql_password",
        "postgresql_port",
        "postgresql_database",
        "postgresql_schema",
        "postgresql_table",
        "postgresql_sslmode",
    ]
    request_serializer_field_names = [
        "postgresql_host",
        "postgresql_username",
        "postgresql_password",
        "postgresql_port",
        "postgresql_database",
        "postgresql_schema",
        "postgresql_table",
        "postgresql_sslmode",
    ]
    # The `postgresql_password` should not be included because it's a secret value that
    # must only be possible to set and not get.
    serializer_field_names = [
        "postgresql_host",
        "postgresql_username",
        "postgresql_port",
        "postgresql_database",
        "postgresql_schema",
        "postgresql_table",
        "postgresql_sslmode",
    ]

    @contextlib.contextmanager
    def _connection(self, instance):
        cursor = None
        connection = None

        baserow_postgresql_connection = (
            settings.BASEROW_PREVENT_POSTGRESQL_DATA_SYNC_CONNECTION_TO_DATABASE
            and are_hostnames_same(
                instance.postgresql_host, settings.DATABASES[DEFAULT_DB_ALIAS]["HOST"]
            )
        )
        data_sync_blacklist = any(
            are_hostnames_same(instance.postgresql_host, hostname)
            for hostname in settings.BASEROW_POSTGRESQL_DATA_SYNC_BLACKLIST
        )

        if baserow_postgresql_connection or data_sync_blacklist:
            raise SyncError("It's not allowed to connect to this hostname.")
        try:
            connection = psycopg.connect(
                host=instance.postgresql_host,
                dbname=instance.postgresql_database,
                user=instance.postgresql_username,
                password=instance.postgresql_password,
                port=instance.postgresql_port,
                sslmode=instance.postgresql_sslmode,
            )
            cursor = connection.cursor()
            yield cursor
        except psycopg.Error as e:
            raise SyncError(str(e))
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def _get_primary_columns(self, cursor, instance: PostgreSQLDataSync) -> list[str]:
        """
        Returns a list of columns that are primary keys for a synchronized table.

        If a table doesn't have primary key, the list will be empty.
        """

        for orimary_key_query in (
            # This query uses pg_catalog, which can change between PostgreSQL version.
            # This should work for cases when a role is not the owner of the table.
            """
                        SELECT a.attname
                        FROM   pg_catalog.pg_index i
                        JOIN   pg_catalog.pg_attribute a ON a.attrelid = i.indrelid
                                AND a.attnum = ANY(i.indkey)
                        JOIN pg_catalog.pg_type t on t.typrelid = i.indrelid
                        JOIN pg_catalog.pg_namespace n on n.oid = t.typnamespace
                        WHERE n.nspname = %s
                          AND t.typname = %s
                          AND    i.indisprimary;
            """,
            # Fallback query, if the first one won't return any results.
            """
                        SELECT kcu.column_name
                        FROM information_schema.table_constraints tc
                                 JOIN information_schema.key_column_usage kcu
                                      ON tc.constraint_name = kcu.constraint_name
                        WHERE tc.table_schema = %s
                          AND tc.table_name = %s
                          AND tc.constraint_type = 'PRIMARY KEY';
            """,
        ):
            cursor.execute(
                orimary_key_query,
                (instance.postgresql_schema, instance.postgresql_table),
            )
            if result := list(cursor.fetchall()):
                return [row[0] for row in result]
        return []

    def _get_table_columns(self, instance):
        with self._connection(instance) as cursor:
            exists_query = """
                SELECT EXISTS (
                   SELECT FROM information_schema.tables
                   WHERE table_schema = %s
                   AND table_name   = %s
                );
            """

            cursor.execute(
                exists_query, (instance.postgresql_schema, instance.postgresql_table)
            )
            exists = cursor.fetchone()
            if not exists[0]:
                raise SyncError(
                    f"The table {instance.postgresql_table} does not exist."
                )

            primary_columns = self._get_primary_columns(cursor, instance)

            columns_query = """
                SELECT column_name, data_type, numeric_scale
                FROM information_schema.columns
                WHERE table_schema = %s
                AND table_name = %s;
            """

            cursor.execute(
                columns_query, (instance.postgresql_schema, instance.postgresql_table)
            )
            columns = cursor.fetchall()

        return primary_columns, columns

    def get_properties(self, instance) -> List[DataSyncProperty]:
        primary_columns, columns = self._get_table_columns(instance)
        properties = []
        for column_name, column_type, decimal_places in columns:
            is_primary = column_name in primary_columns
            property_class = [
                column_type_to_baserow_field_type[key]
                for key in column_type_to_baserow_field_type.keys()
                if key.lower() in column_type.lower()
            ]

            if len(property_class) == 0:
                continue

            property_class = property_class[0]
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
        schema_name = f"{instance.postgresql_schema}"
        table_name = f"{instance.postgresql_table}"
        properties = self.get_properties(instance)
        order_names = [p.key for p in properties if p.unique_primary]
        column_names = [p.key for p in properties]

        with self._connection(instance) as cursor:
            count_query = sql.SQL("SELECT count(*) FROM {}.{}").format(
                sql.Identifier(schema_name), sql.Identifier(table_name)
            )
            cursor.execute(count_query)
            count = cursor.fetchone()[0]

            limit = settings.INITIAL_TABLE_DATA_LIMIT
            if limit and count > settings.INITIAL_TABLE_DATA_LIMIT:
                raise SyncError(f"The table can't contain more than {limit} records.")

            select_query = sql.SQL("SELECT {} FROM {}.{} ORDER BY {}").format(
                sql.SQL(", ").join(map(sql.Identifier, column_names)),
                sql.Identifier(schema_name),
                sql.Identifier(table_name),
                sql.SQL(", ").join(map(sql.Identifier, order_names)),
            )

            cursor.execute(select_query)
            records = cursor.fetchall()

        return [
            {
                p.key: p.prepare_value(record[index])
                for index, p in enumerate(properties)
            }
            for record in records
        ]
