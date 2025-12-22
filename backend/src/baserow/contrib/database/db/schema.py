import contextlib
from typing import Optional, Set

from django.db import connection, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.backends.ddl_references import Statement
from django.db.backends.utils import strip_quotes

from .sql_queries import sql_create_try_cast, sql_drop_try_cast


class PostgresqlLenientDatabaseSchemaEditor:
    """
    Class changes the behavior of the postgres database schema editor slightly. Normally
    when the field type is altered and one of the data columns doesn't have a value that
    can be casted to the new type, it fails. This class introduces the possibility to
    run a custom function, like REGEXP_REPLACE, to convert the data to the correct
    format. If the casting still fails the value will be set to null.
    """

    sql_alter_column_type = (
        "ALTER COLUMN %(column)s TYPE %(type)s%(collation)s "
        "USING pg_temp.try_cast(%(column)s::text)"
    )

    def __init__(
        self,
        *args,
        alter_column_prepare_old_value="",
        alter_column_prepare_new_value="",
        force_alter_column=False,
        **kwargs,
    ):
        self.alter_column_prepare_old_value = alter_column_prepare_old_value
        self.alter_column_prepare_new_value = alter_column_prepare_new_value
        self.force_alter_column = force_alter_column
        super().__init__(*args, **kwargs)

    def _alter_field(
        self,
        model,
        old_field,
        new_field,
        old_type,
        new_type,
        old_db_params,
        new_db_params,
        strict=False,
    ):
        if self.force_alter_column:
            old_type = f"{old_type}_forced"

        if old_type != new_type:
            variables = {}
            if isinstance(self.alter_column_prepare_old_value, tuple):
                alter_column_prepare_old_value, v = self.alter_column_prepare_old_value
                variables = {**variables, **v}
            else:
                alter_column_prepare_old_value = self.alter_column_prepare_old_value

            if isinstance(self.alter_column_prepare_new_value, tuple):
                alter_column_prepare_new_value, v = self.alter_column_prepare_new_value
                variables = {**variables, **v}
            else:
                alter_column_prepare_new_value = self.alter_column_prepare_new_value

            quoted_column_name = self.quote_name(new_field.column)
            for key, value in variables.items():
                variables[key] = value.replace("$FUNCTION$", "")
            self.execute(sql_drop_try_cast)
            self.execute(
                sql_create_try_cast
                % {
                    "column": quoted_column_name,
                    "type": new_type,
                    "alter_column_prepare_old_value": alter_column_prepare_old_value,
                    "alter_column_prepare_new_value": alter_column_prepare_new_value,
                },
                variables,
            )

        return super()._alter_field(
            model,
            old_field,
            new_field,
            old_type,
            new_type,
            old_db_params,
            new_db_params,
            strict,
        )

    def _alter_column_type_sql(
        self, model, old_field, new_field, new_type, old_collation, new_collation
    ):
        # Cast when data type changed.
        # Make ALTER TYPE with SERIAL make sense.
        table = strip_quotes(model._meta.db_table)
        serial_fields_map = {
            "bigserial": "bigint",
            "serial": "integer",
            "smallserial": "smallint",
        }
        if collate_sql := self._collate_sql(
            new_collation, old_collation, model._meta.db_table
        ):
            collate_sql = f" {collate_sql}"
        else:
            collate_sql = ""
        if new_type.lower() in serial_fields_map:
            column = strip_quotes(new_field.column)
            sequence_name = "%s_%s_seq" % (table, column)
            return (
                (
                    self.sql_alter_column_type
                    % {
                        "column": self.quote_name(column),
                        "type": serial_fields_map[new_type.lower()],
                        "collation": collate_sql,
                    },
                    [],
                ),
                [
                    (
                        self.sql_delete_sequence
                        % {
                            "sequence": self.quote_name(sequence_name),
                        },
                        [],
                    ),
                    (
                        self.sql_create_sequence
                        % {
                            "sequence": self.quote_name(sequence_name),
                        },
                        [],
                    ),
                    (
                        self.sql_alter_column
                        % {
                            "table": self.quote_name(table),
                            "changes": self.sql_alter_column_default
                            % {
                                "column": self.quote_name(column),
                                "default": "nextval('%s')"
                                % self.quote_name(sequence_name),
                            },
                        },
                        [],
                    ),
                    (
                        self.sql_set_sequence_max
                        % {
                            "table": self.quote_name(table),
                            "column": self.quote_name(column),
                            "sequence": self.quote_name(sequence_name),
                        },
                        [],
                    ),
                    (
                        self.sql_set_sequence_owner
                        % {
                            "table": self.quote_name(table),
                            "column": self.quote_name(column),
                            "sequence": self.quote_name(sequence_name),
                        },
                        [],
                    ),
                ],
            )
        elif (
            old_field.db_parameters(connection=self.connection)["type"]
            in serial_fields_map
        ):
            # Drop the sequence if migrating away from AutoField.
            column = strip_quotes(new_field.column)
            sequence_name = "%s_%s_seq" % (table, column)
            fragment, _ = BaseDatabaseSchemaEditor._alter_column_type_sql(
                self,
                model,
                old_field,
                new_field,
                new_type,
                old_collation,
                new_collation,
            )
            return fragment, [
                (
                    self.sql_delete_sequence
                    % {
                        "sequence": self.quote_name(sequence_name),
                    },
                    [],
                ),
            ]
        else:
            return BaseDatabaseSchemaEditor._alter_column_type_sql(
                self,
                model,
                old_field,
                new_field,
                new_type,
                old_collation,
                new_collation,
            )

    def _field_should_be_altered(self, old_field, new_field):
        return self.force_alter_column or super()._field_should_be_altered(
            old_field, new_field
        )


@contextlib.contextmanager
def lenient_schema_editor(
    alter_column_prepare_old_value=None,
    alter_column_prepare_new_value=None,
    force_alter_column=False,
):
    """
    A contextual function that yields a modified version of the connection's schema
    editor. This temporary version is more lenient then the regular editor. Normally
    you can't just alter column types to another type if one the values can't be
    casted to the new type. The lenient schema editor can use a custom SQL function
    to convert the value and if it does not succeed the value will be set to null,
    but it will never fail.

    :param alter_column_prepare_old_value: Optionally a query statement converting the
        `p_in` value to a string format.
    :type alter_column_prepare_old_value: None or str
    :param alter_column_prepare_new_value: Optionally a query statement converting the
        `p_in` text value to the new type.
    :type alter_column_prepare_new_value: None or str
    :param force_alter_column: When true forces the schema editor to run an alter
        column statement using the previous two alter_column_prepare parameters.
    :type force_alter_column: bool
    :raises ValueError: When the provided connection is not supported. For now only
        `postgresql` is supported.
    """

    kwargs = {"force_alter_column": force_alter_column}

    if alter_column_prepare_old_value:
        kwargs["alter_column_prepare_old_value"] = alter_column_prepare_old_value

    if alter_column_prepare_new_value:
        kwargs["alter_column_prepare_new_value"] = alter_column_prepare_new_value

    with safe_django_schema_editor(
        name="LenientDatabaseSchemaEditor",
        classes=[PostgresqlLenientDatabaseSchemaEditor],
        **kwargs,
    ) as schema_editor:
        yield schema_editor


def _build_schema_editor_class(name, classes):
    if connection.vendor != "postgresql":
        raise ValueError(
            f"The provided connection vendor is not supported. We only support "
            f"postgres."
        )
    regular_schema_editor = connection.SchemaEditorClass
    schema_editor_class = type(name, (*classes, regular_schema_editor), {})
    return schema_editor_class


@contextlib.contextmanager
def optional_atomic(atomic=True):
    if atomic:
        with transaction.atomic():
            yield
    else:
        yield


class SafeBaserowPostgresSchemaEditor:
    """
    Overrides the create/delete_model methods to work with our link_row fields which
    link back to the same table.
    """

    def create_model(self, model):
        """
        Create a table and any accompanying indexes or unique constraints for
        the given `model`.

        NOTE: this method is a clone of `schema_editor.create_model` with a change:
        it checks if the through table already exists and if it does, it does not try
        to create it again (otherwise we'll end up with a table already exists
        exception). In this way we can create both sides of the m2m relationship for
        self-referencing link_rows when importing data without errors.
        """

        self.create_model_tracking_created_m2ms(model)

    def create_model_tracking_created_m2ms(
        self, model, already_created_through_table_names: Optional[Set[str]] = None
    ):
        sql, params = self.table_sql(model)
        # Prevent using [] as params, in the case a literal '%' is used in the
        # definition
        self.execute(sql, params or None)
        # Add any field index and index_together's
        self.deferred_sql.extend(self._model_indexes_sql(model))
        if already_created_through_table_names is None:
            already_created_through_table_names = set()
        # Make M2M tables
        for field in model._meta.local_many_to_many:
            remote_through = field.remote_field.through
            db_table = remote_through._meta.db_table
            if (
                field.remote_field.through._meta.auto_created
                and db_table not in already_created_through_table_names
            ):
                self.create_model(remote_through)
                already_created_through_table_names.add(db_table)

    def delete_model(self, model):
        """
        Delete a model and any related m2m tables.

        NOTE: this method is a clone of `schema_editor.delete_model` with a change:
        it checks if the through table has already been deleted, it does not try to
        deleted it again (otherwise we'll end up with a table already deleted
        exception).

        In this way we can delete both sides of the m2m relationship for
        self-referencing link_rows.
        """

        # Handle auto-created intermediary models
        already_deleted_through_table_name = set()
        for field in model._meta.local_many_to_many:
            remote_through = field.remote_field.through
            db_table = remote_through._meta.db_table
            if (
                remote_through._meta.auto_created
                and db_table not in already_deleted_through_table_name
            ):
                self.delete_model(field.remote_field.through)
                already_deleted_through_table_name.add(db_table)

        # Delete the table
        self.execute(
            self.sql_delete_table
            % {
                "table": self.quote_name(model._meta.db_table),
            }
        )
        # Remove all deferred statements referencing the deleted table.

        for sql in list(self.deferred_sql):
            if isinstance(sql, Statement) and sql.references_table(
                model._meta.db_table
            ):
                self.deferred_sql.remove(sql)

    def ensure_single_column_index(self, model, field):
        """
        Ensure an index exists on model(field.column). Safe to call repeatedly.
        """

        # If any index/constraint exists that is backed by an index on exactly this
        # column, don't create another.
        if self._constraint_names(model, [field.column], index=True):
            return

        stmt = self._create_index_sql(model, fields=[field])
        self.execute(stmt, params=None)

    def ensure_m2m_field_indexes(self, field):
        if field.many_to_many and field.remote_field.through._meta.auto_created:
            through = field.remote_field.through
            # Ensure the two FK indexes exist (especially important for the "reverse"
            # FK). m2m_field_name() / m2m_reverse_field_name() return the
            # through-field names.
            for through_field_name in (
                field.m2m_field_name(),
                field.m2m_reverse_field_name(),
            ):
                fk_field = through._meta.get_field(through_field_name)
                self.ensure_single_column_index(through, fk_field)

    def add_field(self, model, field):
        return_value = super().add_field(model, field)
        # Using the `create_model` to create a Baserow table, like what we do on
        # `import_serialize` does actually create the indexes of the through table.
        # However, when using `add_field` it does not. The code below will make sure
        # that the needed indexes are created.
        self.ensure_m2m_field_indexes(field)
        return return_value


@contextlib.contextmanager
def safe_django_schema_editor(atomic=True, name=None, classes=None, **kwargs):
    """
    This is a customized version of the django provided Postgres
    BaseDatabaseSchemaEditor. Inside of Baserow this schema editor should always be
    used to prevent the following two bugs:

    1. The django.db.backends.base.schema.BaseDatabaseSchemaEditor.__exit__ has a bug
    where it will not properly call atomic.__exit__ if executing deferred sql
    causes an exception. Instead we disable its internal atomic wrapper which has
    this bug and wrap it ourselves properly and safely.
    2. Our implementation of link_row fields which link back to the same table have to
    add two separate ManyToMany model fields to the Generated baserow django models.
    Because of this the normal shcema_editor.delete_model/create_model functions crash
    as they will try to create or delete the through m2m table twice. This safe
    schema editor overrides these two methods to only create/delete the m2m table once.
    """

    if name is None:
        name = "BaserowSafeDjangoPostgresSchemaEditor"

    if classes is None:
        classes = []

    classes.append(SafeBaserowPostgresSchemaEditor)

    regular_schema_editor = connection.SchemaEditorClass

    if not issubclass(regular_schema_editor, SafeBaserowPostgresSchemaEditor):
        # Only override the connections schema editor if we haven't already done it
        # in an outer safe schema editor context.
        BaserowSafeDjangoPostgresSchemaEditor = _build_schema_editor_class(
            name, classes
        )
        connection.SchemaEditorClass = BaserowSafeDjangoPostgresSchemaEditor

    kwargs.setdefault("connection", connection)

    try:
        with optional_atomic(atomic=atomic):
            with connection.SchemaEditorClass(atomic=False, **kwargs) as schema_editor:
                yield schema_editor
    finally:
        connection.SchemaEditorClass = regular_schema_editor
