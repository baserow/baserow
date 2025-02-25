from copy import deepcopy
from typing import Any, Dict, Optional

from django.core.management.color import no_style
from django.db import connection
from django.db.models import ManyToManyField

from baserow.contrib.database.db.schema import safe_django_schema_editor
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow.core.psycopg import sql

BackupData = Dict[str, Any]


class FieldDataBackupHandler:
    """
    Backs up an arbitrary Baserow field by getting their model fields and deciding how
    to backup based of it. Only the fields data (think cells) is backed up and no
    associated field meta-data is backed up by this class.

    The backup data is stored in the database and
    no serialization/deserialization of the data occurs. So it is fast but
    not suitable for actually backing up the data to prevent data loss, but instead
    useful for backing up the data due to Baserow actions to facilitate undoing them.

    If the model field is a many to many field then we backup by creating a duplicate
    m2m table and copying the data into it.

    Otherwise the field must be an actual column in the user table, so we duplicate
    the column and copy the data into it.

    Also knows how to restore from a backup and clean up any backups done by this
    class even if the Field/Table etc has been permanently deleted from Baserow.
    """

    @classmethod
    def duplicate_field_data(
        cls, original_field: Field, duplicated_field: Field
    ) -> None:
        """
        Duplicates the data of the original field into the duplicated field.
        :param original_field: The original field to duplicate the data from.
        :param duplicated_field: The duplicated field to duplicate the data to.
        """

        model = original_field.table.get_model(
            field_ids=[],
            fields=[original_field, duplicated_field],
            add_dependencies=False,
        )

        original_model_field = model._meta.get_field(original_field.db_column)
        duplicated_model_field = model._meta.get_field(duplicated_field.db_column)
        mapping_values = cls._get_values_map_from_original_to_duplicated(
            original_field, duplicated_field
        )

        if isinstance(original_model_field, ManyToManyField):
            original_through = original_model_field.remote_field.through
            m2m_table_to_duplicate = original_through._meta.db_table
            new_m2m_table_name = (
                duplicated_model_field.remote_field.through._meta.db_table
            )
            cls._copy_m2m_data_between_tables(
                source_table=m2m_table_to_duplicate,
                target_table=new_m2m_table_name,
                m2m_model_field=original_model_field,
                m2m_target_model_field=duplicated_model_field,
                through_model=duplicated_model_field.remote_field.through,
                mapping_values=mapping_values,
            )
        else:
            table_name = original_model_field.model._meta.db_table
            cls._copy_not_null_column_data(
                table_name,
                source_column=original_model_field.column,
                target_column=duplicated_model_field.column,
                mapping_values=mapping_values,
            )

    @classmethod
    def _get_values_map_from_original_to_duplicated(
        cls, original_field, duplicated_field
    ):
        if hasattr(original_field, "select_options"):
            return {
                orig_opt.id: dupl_opt.id
                for orig_opt, dupl_opt in zip(
                    original_field.select_options.all(),
                    duplicated_field.select_options.all(),
                )
            }

    @classmethod
    def backup_field_data(
        cls,
        field_to_backup: Field,
        identifier_to_backup_into: str,
    ) -> BackupData:
        """
        Backs up the provided field's data into a new column or table which will be
        named using the identifier_to_backup_into param.

        :param field_to_backup: A Baserow field that you want to backup the data for.
        :param identifier_to_backup_into: The name that will be used when creating
            the backup column or table.
        :return: A dictionary than can then be passed back into the other class methods
            to restore the backed up data or cleaned it up.
        """

        model = field_to_backup.table.get_model(
            field_ids=[],
            fields=[field_to_backup],
            add_dependencies=False,
        )

        model_field_to_backup = model._meta.get_field(field_to_backup.db_column)

        if isinstance(model_field_to_backup, ManyToManyField):
            through = model_field_to_backup.remote_field.through
            m2m_table_to_backup = through._meta.db_table
            cls._create_duplicate_m2m_table(
                model,
                m2m_model_field_to_duplicate=model_field_to_backup,
                new_m2m_table_name=identifier_to_backup_into,
            )
            cls._copy_m2m_data_between_tables(
                source_table=m2m_table_to_backup,
                target_table=identifier_to_backup_into,
                m2m_model_field=model_field_to_backup,
                through_model=through,
            )
            return {"backed_up_m2m_table_name": identifier_to_backup_into}
        else:
            table_name = model_field_to_backup.model._meta.db_table
            cls._create_duplicate_nullable_column(
                model,
                model_field_to_duplicate=model_field_to_backup,
                new_column_name=identifier_to_backup_into,
            )
            cls._copy_not_null_column_data(
                table_name,
                source_column=model_field_to_backup.column,
                target_column=identifier_to_backup_into,
            )
            return {
                "table_id_containing_backup_column": field_to_backup.table_id,
                "backed_up_column_name": identifier_to_backup_into,
            }

    @classmethod
    def restore_backup_data_into_field(
        cls,
        field_to_restore_backup_data_into: Field,
        backup_data: BackupData,
    ):
        """
        Given a dictionary generated by the backup_field_data this method copies the
        backed up data back into an existing Baserow field of the same type.
        """

        model = field_to_restore_backup_data_into.table.get_model(
            field_ids=[],
            fields=[field_to_restore_backup_data_into],
            add_dependencies=False,
        )
        model_field_to_restore_into = model._meta.get_field(
            field_to_restore_backup_data_into.db_column
        )
        if isinstance(model_field_to_restore_into, ManyToManyField):
            backed_up_m2m_table_name = backup_data["backed_up_m2m_table_name"]
            through = model_field_to_restore_into.remote_field.through
            target_m2m_table = through._meta.db_table

            cls._truncate_table(target_m2m_table)
            cls._copy_m2m_data_between_tables(
                source_table=backed_up_m2m_table_name,
                target_table=target_m2m_table,
                m2m_model_field=model_field_to_restore_into,
                through_model=through,
            )
            cls._drop_table(backed_up_m2m_table_name)
        else:
            backed_up_column_name = backup_data["backed_up_column_name"]
            table_name = model_field_to_restore_into.model._meta.db_table
            cls._copy_not_null_column_data(
                table_name,
                source_column=backed_up_column_name,
                target_column=model_field_to_restore_into.column,
            )
            cls._drop_column(table_name, backed_up_column_name)

    @classmethod
    def clean_up_backup_data(
        cls,
        backup_data: BackupData,
    ):
        """
        Given a dictionary generated by the backup_field_data this method deletes any
        backup data to reclaim space used.
        """

        if "backed_up_m2m_table_name" in backup_data:
            cls._drop_table(backup_data["backed_up_m2m_table_name"])
        else:
            try:
                table = Table.objects_and_trash.get(
                    id=backup_data["table_id_containing_backup_column"]
                )
                cls._drop_column(
                    table.get_database_table_name(),
                    backup_data["backed_up_column_name"],
                )
            except Table.DoesNotExist:
                # The table has already been permanently deleted by the trash system
                # so there is nothing for us to do.
                pass

    @staticmethod
    def _create_duplicate_m2m_table(
        model: GeneratedTableModel,
        m2m_model_field_to_duplicate: ManyToManyField,
        new_m2m_table_name: str,
    ):
        with safe_django_schema_editor() as schema_editor:
            # Create a duplicate m2m table to backup the data into.
            new_backup_table = deepcopy(m2m_model_field_to_duplicate)
            new_backup_table.remote_field.through._meta.db_table = new_m2m_table_name
            schema_editor.add_field(model, new_backup_table)

    @staticmethod
    def _truncate_table(target_table):
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("TRUNCATE TABLE {target_table}").format(
                    target_table=sql.Identifier(target_table),
                )
            )

    @staticmethod
    def _drop_table(backup_name: str):
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("DROP TABLE {backup_table}").format(
                    backup_table=sql.Identifier(backup_name),
                )
            )

    @classmethod
    def _get_source_column_sql_with_mapping(
        cls, source_column: str, mapping: Optional[Dict[int, int]] = None
    ):
        if not mapping:
            return sql.Identifier(source_column)
        case_when_sql = sql.SQL(" ").join(
            sql.SQL("WHEN {source_value} THEN {target_value}").format(
                source_value=sql.Literal(source_value),
                target_value=sql.Literal(target_value),
            )
            for source_value, target_value in mapping.items()
        )
        return sql.SQL("CASE {source_column} {case_when_sql} END").format(
            source_column=sql.Identifier(source_column),
            case_when_sql=case_when_sql,
        )

    @classmethod
    def _copy_m2m_data_between_tables(
        cls,
        source_table: str,
        target_table: str,
        m2m_model_field: ManyToManyField,
        through_model: GeneratedTableModel,
        m2m_target_model_field: Optional[ManyToManyField] = None,
        mapping_values: Optional[Dict[int, int]] = None,
    ):
        with connection.cursor() as cursor:
            m2m_target_model_field = m2m_target_model_field or m2m_model_field
            m2m_reverse_column = cls._get_source_column_sql_with_mapping(
                m2m_model_field.m2m_reverse_name(), mapping_values
            )
            cursor.execute(
                sql.SQL(
                    """
                INSERT INTO {target_table} (id, {m2m_column}, {m2m_reverse_target_column})
                SELECT id, {m2m_column}, {m2m_reverse_column} FROM {source_table}
                """
                ).format(
                    source_table=sql.Identifier(source_table),
                    target_table=sql.Identifier(target_table),
                    m2m_column=sql.Identifier(m2m_model_field.m2m_column_name()),
                    m2m_reverse_column=m2m_reverse_column,
                    m2m_reverse_target_column=sql.Identifier(
                        m2m_target_model_field.m2m_reverse_name()
                    ),
                )
            )
            # When the rows are inserted we keep the provide the old ids and because of
            # that the auto increment is still set at `1`. This needs to be set to the
            # maximum value because otherwise creating a new row could later fail.
            sequence_sql = connection.ops.sequence_reset_sql(
                no_style(), [through_model]
            )
            cursor.execute(sequence_sql[0])

    @staticmethod
    def _create_duplicate_nullable_column(
        model: GeneratedTableModel, model_field_to_duplicate, new_column_name: str
    ):
        with safe_django_schema_editor() as schema_editor:
            # Create a duplicate column to backup the data into.
            new_backup_model_field = deepcopy(model_field_to_duplicate)
            new_backup_model_field.column = new_column_name
            # It must be nullable so INSERT's into the table still work. If we restore
            # this backed up column back into a real column we won't copy over any
            # NULLs created by INSERTs.
            new_backup_model_field.null = True
            schema_editor.add_field(model, new_backup_model_field)

    @classmethod
    def _copy_not_null_column_data(
        cls, table_name, source_column, target_column, mapping_values=None
    ):
        source_column_sql = cls._get_source_column_sql_with_mapping(
            source_column, mapping_values
        )

        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL(
                    "UPDATE {table_name} SET {target_column} = {source_column} "
                    "WHERE {source_column} IS NOT NULL"
                ).format(
                    table_name=sql.Identifier(table_name),
                    target_column=sql.Identifier(target_column),
                    source_column=source_column_sql,
                )
            )

    @staticmethod
    def _drop_column(table_name: str, column_to_drop: str):
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("ALTER TABLE {table_name} DROP COLUMN {column_to_drop}").format(
                    table_name=sql.Identifier(table_name),
                    column_to_drop=sql.Identifier(column_to_drop),
                )
            )
