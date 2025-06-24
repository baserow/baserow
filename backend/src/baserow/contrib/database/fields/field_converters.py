from dataclasses import dataclass

from django.db import models, transaction

from baserow.contrib.database.db.schema import (
    lenient_schema_editor,
    safe_django_schema_editor,
)
from baserow.core.psycopg import sql

from .models import (
    AutonumberField,
    FileField,
    FormulaField,
    LinkRowField,
    MultipleCollaboratorsField,
    MultipleSelectField,
    PasswordField,
    SelectOption,
    SingleSelectField,
)
from .registries import FieldConverter, field_type_registry


class RecreateFieldConverter(FieldConverter):
    def alter_field(
        self,
        from_field,
        to_field,
        from_model,
        to_model,
        from_model_field,
        to_model_field,
        user,
        connection,
        **kwargs,
    ):
        """
        Does the field alteration by removing the old field and creating the new field.
        The success rate of this converter is very high, but the downside is that the
        data is lost.
        """

        with safe_django_schema_editor() as schema_editor:
            schema_editor.remove_field(from_model, from_model_field)
            schema_editor.add_field(to_model, to_model_field)


class FormulaFieldConverter(RecreateFieldConverter):
    type = "formula"

    def alter_field(
        self,
        from_field,
        to_field,
        from_model,
        to_model,
        from_model_field,
        to_model_field,
        user,
        connection,
        force_recreate_column=False,
    ):
        """
        Recreates the underlying column if the formula field type has changed or if
        something else has changed that requires the column to be recreated. This will
        prevent unnecessary ALTER TABLE statements from being executed, so updating a
        formula field will be faster and won't lock the table requiring an ACCESS
        EXCLUSIVE lock.
        """

        from baserow.contrib.database.fields.field_types import FormulaFieldType

        if isinstance(from_field, FormulaField):
            (
                from_field_instance,
                from_field_type,
            ) = FormulaFieldType().get_field_instance_and_type_from_formula_field(
                from_field
            )
            (
                to_field_instance,
                to_field_type,
            ) = FormulaFieldType().get_field_instance_and_type_from_formula_field(
                to_field
            )
            formula_field_type_changed = from_field_type.type != to_field_type.type
            db_index_changed = from_field.db_index != to_field.db_index

            def has_different_db_column_attrs():
                return any(
                    [
                        getattr(from_field_instance, attr)
                        != getattr(to_field_instance, attr)
                        for attr in from_field_type.db_column_fields
                    ]
                )

            recreate_field = (
                formula_field_type_changed
                or db_index_changed
                or from_field.error
                or has_different_db_column_attrs()
                or force_recreate_column
            )
        else:
            recreate_field = True

        if recreate_field:
            super().alter_field(
                from_field,
                to_field,
                from_model,
                to_model,
                from_model_field,
                to_model_field,
                user,
                connection,
            )

    def is_applicable(self, from_model, from_field, to_field):
        return isinstance(to_field, FormulaField)


class AutonumberFieldConverter(RecreateFieldConverter):
    type = "autonumber"

    def is_applicable(self, from_model, from_field, to_field):
        from_autonumber = isinstance(from_field, AutonumberField)
        to_autonumber = isinstance(to_field, AutonumberField)
        return to_autonumber and not from_autonumber


class PasswordFieldConverter(RecreateFieldConverter):
    type = "password"

    def is_applicable(self, from_model, from_field, to_field):
        # For now, we always want to recreate the whole field is it's changed to or
        # from a password field because it can take quite long to create many hashed
        # when converting from a text to a password field.
        from_password = isinstance(from_field, PasswordField)
        to_password = isinstance(to_field, PasswordField)
        return to_password or from_password


class LinkRowFieldConverter(RecreateFieldConverter):
    type = "link_row"

    def is_applicable(self, from_model, from_field, to_field):
        return (
            (
                isinstance(from_field, LinkRowField)
                and not isinstance(to_field, LinkRowField)
            )
            or (
                not isinstance(from_field, LinkRowField)
                and isinstance(to_field, LinkRowField)
            )
            or (
                # If both fields are LinkRowFields and neither the linked table nor the
                # multiple setting has changed.
                isinstance(from_field, LinkRowField)
                and isinstance(to_field, LinkRowField)
                and from_field.link_row_table_id != to_field.link_row_table_id
            )
        )


class MultipleCollaboratorsFieldConverter(RecreateFieldConverter):
    type = "multiple_collaborators"

    def is_applicable(self, from_model, from_field, to_field):
        return (
            isinstance(to_field, MultipleCollaboratorsField)
            and not isinstance(from_field, MultipleCollaboratorsField)
        ) or (
            isinstance(from_field, MultipleCollaboratorsField)
            and not isinstance(to_field, MultipleCollaboratorsField)
        )


class FileFieldConverter(RecreateFieldConverter):
    type = "file"

    def is_applicable(self, from_model, from_field, to_field):
        return (
            isinstance(from_field, FileField) and not isinstance(to_field, FileField)
        ) or (not isinstance(from_field, FileField) and isinstance(to_field, FileField))


@dataclass
class MultipleSelectConversionConfig:
    """Dataclass for holding several configuration options"""

    text_delimiter: str = ","
    text_delimiter_output: str = ", "
    quote_sign: str = '"'
    # This value determines how many unique values
    # are accepted as new select_options.
    # If there are more unique values then there
    # will be no conversion.
    new_select_options_threshold: int = 100
    # This regex can be used in Postgres regex functions.
    # It makes sure that a string is split by comma
    # while ignoring commas inside 'quote_sign'
    regex_split: str = ',\\s?(?=(?:[^"]*"[^"]*")*[^"]*$)'
    trim_empty_and_quote: str = f" {quote_sign}"
    text_delimiter_search: str = f"%{text_delimiter}%"
    allowed_select_options_length: int = SelectOption.get_max_value_length()


class MultipleSelectConversionBase(MultipleSelectConversionConfig):
    """
    Base class with specific helper methods which holds all the information and
    configuration that is needed in a conversion from a multiple select field to
    another field type, as well as in a conversion from another field type to a
    multiple select field.
    """

    def __init__(
        self,
        from_field,
        to_field,
        from_model_field,
        to_model_field,
    ):
        if isinstance(to_field, MultipleSelectField):
            self.multiple_select_field = to_field
            self.multiple_select_model_field = to_model_field
        else:
            self.multiple_select_field = from_field
            self.multiple_select_model_field = from_model_field
        self.through_model = self.multiple_select_model_field.remote_field.through
        self.through_table_fields = self.through_model._meta.get_fields()
        self.through_table_name = self.through_model._meta.db_table
        self.through_table_column_name = self.through_table_fields[
            1
        ].get_attname_column()[1]
        self.through_select_option_column_name = self.through_table_fields[
            2
        ].get_attname_column()[1]

    def insert_into_many_relationship(
        self,
        connection,
        subselect: sql.SQL,
    ):
        """
        Helper method in order to insert values into the many to many through table.

        It expects a subselect with two columns representing the values to be inserted:

        select table_row_id, select_option_id from x

        It is required that the select options exists before this query runs.
        """

        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("insert into {table} ({column_1}, {column_2}) {vals}").format(
                    table=sql.Identifier(self.through_table_name),
                    column_1=sql.Identifier(self.through_table_column_name),
                    column_2=sql.Identifier(self.through_select_option_column_name),
                    vals=subselect,
                ),
            )

    @staticmethod
    def update_column_with_values(
        connection, values: sql.SQL, table: str, db_column: str
    ):
        """
        Helper method in order to update a table column with a list of values. This is
        needed when converting to a field_type which has it's own column in the table
        and we want to insert the values from the multiple_select field at the specific
        rows.

        It expects a subselect with two columns representing the values to be inserted:

        select table_row_id, value_to_be_inserted from x
        """

        update_stmt = sql.SQL(
            """
            update {table} as u
                set {db_column} = vals.new_value
            from ({values_list}) as vals(id, new_value)
            where vals.id = u.id
            """
        ).format(
            table=sql.Identifier(table),
            db_column=sql.Identifier(db_column),
            values_list=values,
        )
        with connection.cursor() as cursor:
            cursor.execute(update_stmt)

    @staticmethod
    def add_temporary_text_field_to_model(model, db_column):
        """
        Adds a temporary text field to the given model with the provided db_column name.
        """

        tmp_field_name = "tmp_" + db_column
        models.TextField(
            null=True, blank=True, db_column=db_column
        ).contribute_to_class(model, tmp_field_name)
        tmp_model_field = model._meta.get_field(tmp_field_name)

        return tmp_model_field, tmp_field_name


class TextFieldToMultipleSelectFieldConverter(FieldConverter):
    """
    This is a converter class for converting from any Text, Number or DateField to a
    MultipleSelectField.

    When converting from any of the mentioned FieldTypes we want to make sure that the
    their values get correctly converted to the destination field type. We make use of
    the lenient_schema editor here, as well as the "get_alter_column_prepare_old_value"
    function of the respective field type.

    In order to actually convert the values, a temporary text column is being created
    which will be the receiver column of the conversion with the lenient_schema_editor
    and the "get_alter_column_prepare_old_value" function. The from_field gets
    converted to a temporary text column.

    Afterwards this temporary text column will be the source for the select_options that
    have to be created.
    """

    type = "text_to_multiple_select"

    def is_applicable(self, from_model, from_field, to_field):
        return (
            not isinstance(from_field, MultipleSelectField)
            and not isinstance(from_field, SingleSelectField)
            and isinstance(to_field, MultipleSelectField)
        )

    def alter_field(
        self,
        from_field,
        to_field,
        from_model,
        to_model,
        from_model_field,
        to_model_field,
        user,
        connection,
    ):
        from_field_type = field_type_registry.get_by_model(from_field)
        helper = MultipleSelectConversionBase(
            from_field,
            to_field,
            from_model_field,
            to_model_field,
        )

        # The lenient_schema_editor is needed so that field type specific conversions
        # will be respected when converting to a MultipleSelectField.
        with lenient_schema_editor(
            from_field_type.get_alter_column_prepare_old_value(
                connection, from_field, to_field
            ),
            None,
        ) as schema_editor:
            # Convert the existing column to a temporary text field.
            tmp_model_field, _ = helper.add_temporary_text_field_to_model(
                to_model, from_field.db_column
            )
            schema_editor.alter_field(to_model, from_model_field, tmp_model_field)

            # Add the MultipleSelect field to the table
            schema_editor.add_field(to_model, to_model_field)

            # Since we are converting to a multiple select field we might have to
            # create select options before we can then populate the table with the
            # given select options.
            values_query = sql.SQL(
                """
                    SELECT
                        sub.id,
                        opt.id
                    FROM (
                        SELECT
                            left(
                                trim(both {trimmed} from distinct_value),
                                {select_options_length}
                            ) as value,
                            id
                        FROM
                            (
                            SELECT
                                a.elem as distinct_value,
                                t.id as id,
                                min(index) as first_index
                            FROM
                                {table_name} as t
                            LEFT JOIN LATERAL
                                unnest(
                                    regexp_split_to_array({table_column_name}, {regex}))
                                with ordinality as a(elem, index) on true
                            GROUP BY
                                a.elem,
                                t.id
                            ) as innersub
                        order by
                            first_index
                        ) as sub
                    INNER JOIN database_selectoption opt ON
                        opt.value = sub.value
                    WHERE opt.field_id = {field_id}
                """
            ).format(
                field_id=sql.Literal(to_field.id),
                table_name=sql.Identifier(to_model._meta.db_table),
                table_column_name=sql.Identifier(
                    tmp_model_field.get_attname_column()[1]
                ),
                trimmed=sql.Literal(helper.trim_empty_and_quote),
                regex=sql.Literal(helper.regex_split),
                select_options_length=sql.Literal(helper.allowed_select_options_length),
            )

            # If the amount of unique new select_options that need to be created is
            # lower than the allowed threshold and the user has not provided any
            # select_options themselves, we need to extract the options and create them.
            with transaction.atomic():
                helper.insert_into_many_relationship(connection, values_query)
            schema_editor.remove_field(to_model, tmp_model_field)


class MultipleSelectFieldToTextFieldConverter(FieldConverter):
    """
    This is a converter class for converting a MultipleSelectField to any Text, Number
    or DateField.

    When converting to any of the mentioned FieldTypes we want to make sure that the
    values inserted as a select_option to the MultipleSelectFieldType get correctly
    converted to the destination field type. We make use of the lenient_schema editor
    here, as well as the "get_alter_column_prepare_new_value" function of the respective
    field type.

    In order to actually convert the values, a temporary column is being created which
    is first updated with the aggregated values of the MultipleSelectFieldType.
    Afterwards this temporary column gets converted with the lenient_schema editor.
    """

    type = "multiple_select_to_text"

    def is_applicable(self, from_model, from_field, to_field):
        return (
            isinstance(from_field, MultipleSelectField)
            and not isinstance(to_field, MultipleSelectField)
            and not isinstance(to_field, SingleSelectField)
        )

    def alter_field(
        self,
        from_field,
        to_field,
        from_model,
        to_model,
        from_model_field,
        to_model_field,
        user,
        connection,
    ):
        to_field_type = field_type_registry.get_by_model(to_field)
        helper = MultipleSelectConversionBase(
            from_field,
            to_field,
            from_model_field,
            to_model_field,
        )
        with lenient_schema_editor(
            None,
            to_field_type.get_alter_column_prepare_new_value(
                connection, from_field, to_field
            ),
        ) as schema_editor:
            tmp_model_field, _ = helper.add_temporary_text_field_to_model(
                from_model, from_field.db_column
            )
            schema_editor.add_field(from_model, tmp_model_field)
            aggregated_multiple_select_values = sql.SQL(
                """
                    select
                        tab.id as row_id,
                        string_agg(
                            case when ds.value like {text_delimiter_search}
                                then concat({quote}, ds.value, {quote})
                                else ds.value
                            end, {delimiter_output}
                            order by dm.id
                        ) as agg_value
                    from
                        {table} tab
                    inner join {through_table} dm on
                        tab.id = dm.{table_column}
                    inner join database_selectoption ds on
                        ds.id = dm.{select_option_column}
                    group by
                        tab.id
                """
            ).format(
                table=sql.Identifier(from_model._meta.db_table),
                through_table=sql.Identifier(helper.through_table_name),
                table_column=sql.Identifier(helper.through_table_column_name),
                select_option_column=sql.Identifier(
                    helper.through_select_option_column_name
                ),
                delimiter_output=sql.Literal(helper.text_delimiter_output),
                text_delimiter_search=sql.Literal(helper.text_delimiter_search),
                quote=sql.Literal(helper.quote_sign),
            )

            helper.update_column_with_values(
                connection,
                aggregated_multiple_select_values,
                from_model._meta.db_table,
                tmp_model_field.db_column,
            )
            schema_editor.remove_field(from_model, from_model_field)
            schema_editor.alter_field(from_model, tmp_model_field, to_model_field)


class MultipleSelectFieldToSingleSelectFieldConverter(FieldConverter):
    """
    Conversion class for converting a MultipleSelectField to a SingleSelectField. When
    converting from a MultipleSelectField we want to keep the already added select
    options on the field, but make sure that the first added select option on any
    given row will be the one that will be added to the SingleSelectField.
    """

    type = "multiple_select_to_single_select"

    def is_applicable(self, from_model, from_field, to_field):
        return isinstance(from_field, MultipleSelectField) and isinstance(
            to_field, SingleSelectField
        )

    def alter_field(
        self,
        from_field,
        to_field,
        from_model,
        to_model,
        from_model_field,
        to_model_field,
        user,
        connection,
    ):
        helper = MultipleSelectConversionBase(
            from_field,
            to_field,
            from_model_field,
            to_model_field,
        )
        with safe_django_schema_editor() as schema_editor:
            schema_editor.add_field(to_model, to_model_field)

        multiple_select_first_value_query = sql.SQL(
            """
            with summary as (
                select
                    tab.id as row_id,
                    ds.value as option_val,
                    ds.id as option_id,
                    dm.id as rel_id,
                    row_number() over(partition by tab.id
                    order by
                        dm.id asc) as rank
                from
                    {table} tab
                inner join {through_table} dm on
                    tab.id = dm.{table_column}
                inner join database_selectoption ds on
                    ds.id = dm.{select_option_column}
            )
            select
                row_id,
                option_id
            from
                summary
            where
                rank = 1
            """
        ).format(
            table=sql.Identifier(from_model._meta.db_table),
            through_table=sql.Identifier(helper.through_table_name),
            table_column=sql.Identifier(helper.through_table_column_name),
            select_option_column=sql.Identifier(
                helper.through_select_option_column_name
            ),
        )

        helper.update_column_with_values(
            connection,
            multiple_select_first_value_query,
            to_model._meta.db_table,
            to_field.db_column,
        )

        with safe_django_schema_editor() as schema_editor:
            schema_editor.remove_field(from_model, from_model_field)


class SingleSelectFieldToMultipleSelectFieldConverter(FieldConverter):
    """
    Conversion class for converting a SingleSelectField to a MultipleSelectField. When
    converting from a SingleSelectField we want to keep the already added select
    options on the field and make sure that the added select option on the
    SingleSelectField will be added to the MultipleSelectField.
    """

    type = "single_select_to_multiple_select"

    def is_applicable(self, from_model, from_field, to_field):
        return isinstance(from_field, SingleSelectField) and isinstance(
            to_field, MultipleSelectField
        )

    def alter_field(
        self,
        from_field,
        to_field,
        from_model,
        to_model,
        from_model_field,
        to_model_field,
        user,
        connection,
    ):
        helper = MultipleSelectConversionBase(
            from_field,
            to_field,
            from_model_field,
            to_model_field,
        )
        with safe_django_schema_editor() as schema_editor:
            schema_editor.add_field(to_model, to_model_field)

        query = sql.SQL(
            """
            select
                id, {from_field_name}
            from {from_table_name}
            where
                {from_field_name} is not null
            """
        ).format(
            from_field_name=sql.Identifier(from_model_field.name),
            from_table_name=sql.Identifier(from_model._meta.db_table),
        )

        helper.insert_into_many_relationship(
            connection,
            query,
        )

        with safe_django_schema_editor() as schema_editor:
            schema_editor.remove_field(from_model, from_model_field)
