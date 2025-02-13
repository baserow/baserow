from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from django.core.exceptions import ValidationError

from baserow.contrib.database.export_serialized import DatabaseExportSerializedStructure
from baserow.contrib.database.fields.models import (
    NUMBER_MAX_DECIMAL_PLACES,
    BooleanField,
    CountField,
    CreatedOnField,
    DateField,
    EmailField,
    Field,
    FileField,
    LastModifiedField,
    LinkRowField,
    LongTextField,
    MultipleSelectField,
    NumberField,
    PhoneNumberField,
    RatingField,
    SingleSelectField,
    TextField,
    URLField,
)
from baserow.contrib.database.fields.registries import field_type_registry

from .config import AirtableImportConfig
from .helpers import import_airtable_date_type_options, set_select_options_on_field
from .import_report import (
    ERROR_TYPE_DATA_TYPE_MISMATCH,
    ERROR_TYPE_UNSUPPORTED_FEATURE,
    SCOPE_CELL,
    SCOPE_FIELD,
    AirtableImportReport,
)
from .registry import AirtableColumnType
from .utils import get_airtable_row_primary_value


class TextAirtableColumnType(AirtableColumnType):
    type = "text"

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        validator_name = raw_airtable_column.get("typeOptions", {}).get("validatorName")
        if validator_name == "url":
            return URLField()
        elif validator_name == "email":
            return EmailField()
        else:
            return TextField()

    def to_baserow_export_serialized_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_row,
        raw_airtable_column,
        baserow_field,
        value,
        files_to_download,
        config,
        import_report,
    ):
        if isinstance(baserow_field, (EmailField, URLField)):
            try:
                field_type = field_type_registry.get_by_model(baserow_field)
                field_type.validator(value)
            except ValidationError:
                row_name = get_airtable_row_primary_value(
                    raw_airtable_table, raw_airtable_row
                )
                import_report.add_failed(
                    f"Row: \"{row_name}\", field: \"{raw_airtable_column['name']}\"",
                    SCOPE_CELL,
                    raw_airtable_table["name"],
                    ERROR_TYPE_DATA_TYPE_MISMATCH,
                    f'Cell value "{value}" was left empty because it didn\'t pass the email or URL validation.',
                )
                return ""

        return value


class MultilineTextAirtableColumnType(AirtableColumnType):
    type = "multilineText"

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        return LongTextField()


class RichTextTextAirtableColumnType(AirtableColumnType):
    type = "richText"

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        return LongTextField()

    def to_baserow_export_serialized_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_row,
        raw_airtable_column,
        baserow_field,
        value,
        files_to_download,
        config,
        import_report,
    ):
        # We don't support rich text formatting yet, so this converts the value to
        # plain text.
        rich_values = []
        for v in value["documentValue"]:
            insert_value = v["insert"]
            if isinstance(insert_value, str):
                rich_values.append(insert_value)
            elif isinstance(insert_value, dict):
                rich_value = self._extract_value_from_airtable_rich_value_dict(
                    insert_value
                )
                if rich_value is not None:
                    rich_values.append(rich_value)

        return "".join(rich_values)

    def _extract_value_from_airtable_rich_value_dict(
        self, insert_value_dict: Dict[Any, Any]
    ) -> Optional[str]:
        """
        Airtable rich text fields can contain references to users. For now this method
        attempts to return a @userId reference string. In the future if Baserow has
        a rich text field and the ability to reference users in them we should map
        this airtable userId to the corresponding Baserow user id.
        """

        mention = insert_value_dict.get("mention")
        if isinstance(mention, dict):
            user_id = mention.get("userId")
            if user_id is not None:
                return f"@{user_id}"


class NumberAirtableColumnType(AirtableColumnType):
    type = "number"

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        type_options = raw_airtable_column.get("typeOptions", {})
        decimal_places = 0

        if type_options.get("format", "integer") == "decimal":
            # Minimum of 1 and maximum of 5 decimal places.
            decimal_places = min(
                max(1, type_options.get("precision", 1)), NUMBER_MAX_DECIMAL_PLACES
            )

        return NumberField(
            number_decimal_places=decimal_places,
            number_negative=type_options.get("negative", True),
        )

    def to_baserow_export_serialized_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_row,
        raw_airtable_column,
        baserow_field,
        value,
        files_to_download,
        config,
        import_report,
    ):
        if value is not None:
            value = Decimal(value)

        if value is not None and not baserow_field.number_negative and value < 0:
            value = None

        return None if value is None else str(value)


class RatingAirtableColumnType(AirtableColumnType):
    type = "rating"

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        return RatingField(
            max_value=raw_airtable_column.get("typeOptions", {}).get("max", 5)
        )


class CheckboxAirtableColumnType(AirtableColumnType):
    type = "checkbox"

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        return BooleanField()

    def to_baserow_export_serialized_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_row,
        raw_airtable_column,
        baserow_field,
        value,
        files_to_download,
        config,
        import_report,
    ):
        return "true" if value else "false"


class DateAirtableColumnType(AirtableColumnType):
    type = "date"

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        type_options = raw_airtable_column.get("typeOptions", {})
        # Check if a timezone is provided in the type options, if so, we might want
        # to use that timezone for the conversion later on.
        airtable_timezone = type_options.get("timeZone", None)
        date_show_tzinfo = type_options.get("shouldDisplayTimeZone", False)

        # date_force_timezone=None it the equivalent of airtable_timezone="client".
        if airtable_timezone == "client":
            import_report.add_failed(
                raw_airtable_column["name"],
                SCOPE_FIELD,
                raw_airtable_table.get("name", ""),
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                "The date field was imported, but the client timezone setting was dropped.",
            )
            airtable_timezone = None

        return DateField(
            date_show_tzinfo=date_show_tzinfo,
            date_force_timezone=airtable_timezone,
            **import_airtable_date_type_options(type_options),
        )

    def to_baserow_export_serialized_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_row,
        raw_airtable_column,
        baserow_field,
        value,
        files_to_download,
        config,
        import_report,
    ):
        if value is None:
            return value

        try:
            value = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
                tzinfo=timezone.utc
            )
        except ValueError as e:
            row_name = get_airtable_row_primary_value(
                raw_airtable_table, raw_airtable_row
            )
            import_report.add_failed(
                f"Row: \"{row_name}\", field: \"{raw_airtable_column['name']}\"",
                SCOPE_CELL,
                raw_airtable_table["name"],
                ERROR_TYPE_DATA_TYPE_MISMATCH,
                f'Cell value was left empty because it didn\'t pass the datetime validation with error: "{str(e)}"',
            )
            return None

        if baserow_field.date_include_time:
            return f"{value.isoformat()}"
        else:
            # WORKAROUND: if the year value is < 1000, Python has a bug that will not
            # add leading zeros to generate the year in four digits format, hence,
            # we're adding the missing zeros if needed. source:
            # https://stackoverflow.com/questions/71118275/parsing-three-digit-years-using-datetime
            formatted_date = value.strftime("%Y-%m-%d")
            zeros = 4 - formatted_date.index("-")
            if zeros:
                formatted_date = f"{'0' * zeros}{formatted_date}"
            return formatted_date


class FormulaAirtableColumnType(AirtableColumnType):
    type = "formula"

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        type_options = raw_airtable_column.get("typeOptions", {})
        display_type = type_options.get("displayType", "")
        airtable_timezone = type_options.get("timeZone", None)
        date_show_tzinfo = type_options.get("shouldDisplayTimeZone", False)

        is_last_modified = display_type == "lastModifiedTime"
        is_created = display_type == "createdTime"

        if is_last_modified or is_created and airtable_timezone == "client":
            import_report.add_failed(
                raw_airtable_column["name"],
                SCOPE_FIELD,
                raw_airtable_table.get("name", ""),
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                "The field was imported, but the client timezone setting was dropped.",
            )

        # date_force_timezone=None it the equivalent of airtable_timezone="client".
        if airtable_timezone == "client":
            airtable_timezone = None

        # The formula conversion isn't support yet, but because the Created on and
        # Last modified fields work as a formula, we can convert those.
        if is_last_modified:
            return LastModifiedField(
                date_show_tzinfo=date_show_tzinfo,
                date_force_timezone=airtable_timezone,
                **import_airtable_date_type_options(type_options),
            )
        elif is_created:
            return CreatedOnField(
                date_show_tzinfo=date_show_tzinfo,
                date_force_timezone=airtable_timezone,
                **import_airtable_date_type_options(type_options),
            )

    def to_baserow_export_serialized_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_row,
        raw_airtable_column,
        baserow_field,
        value,
        files_to_download,
        config,
        import_report,
    ):
        if isinstance(baserow_field, CreatedOnField):
            # If `None`, the value will automatically be populated from the
            # `created_on` property of the row when importing, which already contains
            # the correct value.
            return None
        if isinstance(baserow_field, LastModifiedField):
            # Because there isn't a last modified property in the Airtable data,
            # we must use the value as provided here.
            return (
                datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
                .replace(tzinfo=timezone.utc)
                .isoformat()
            )


class ForeignKeyAirtableColumnType(AirtableColumnType):
    type = "foreignKey"

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        type_options = raw_airtable_column.get("typeOptions", {})
        foreign_table_id = type_options.get("foreignTableId")

        return LinkRowField(
            link_row_table_id=foreign_table_id,
            link_row_related_field_id=type_options.get("symmetricColumnId"),
        )

    def to_baserow_export_serialized_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_row,
        raw_airtable_column,
        baserow_field,
        value,
        files_to_download,
        config,
        import_report,
    ):
        foreign_table_id = raw_airtable_column["typeOptions"]["foreignTableId"]

        # Airtable doesn't always provide an object with a `foreignRowId`. This can
        # happen with a synced table for example. Because we don't have access to the
        # source in that case, we need to skip them.
        foreign_row_ids = [v["foreignRowId"] for v in value if "foreignRowId" in v]

        value = []
        for foreign_row_id in foreign_row_ids:
            try:
                value.append(row_id_mapping[foreign_table_id][foreign_row_id])
            except KeyError:
                # If a key error is raised, then we don't have the foreign row id in
                # the mapping. This can happen if the data integrity is compromised in
                # the Airtable base. We don't want to fail the import, so we're
                # reporting instead.
                row_name = get_airtable_row_primary_value(
                    raw_airtable_table, raw_airtable_row
                )
                import_report.add_failed(
                    f"Row: \"{row_name}\", field: \"{raw_airtable_column['name']}\"",
                    SCOPE_CELL,
                    raw_airtable_table["name"],
                    ERROR_TYPE_DATA_TYPE_MISMATCH,
                    f'Foreign row id "{foreign_row_id}" was not added as relationship in the cell value was because it was not found in the mapping.',
                )

        return value


class MultipleAttachmentAirtableColumnType(AirtableColumnType):
    type = "multipleAttachment"

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        return FileField()

    def to_baserow_export_serialized_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_row,
        raw_airtable_column,
        baserow_field,
        value,
        files_to_download,
        config,
        import_report,
    ):
        new_value = []

        # Skip adding the files to the `files_to_download` object and to the value,
        # so that they're completely ignored if desired.
        if config.skip_files:
            return new_value

        for file in value:
            file_name = "_".join(file["url"].split("/")[-3:])
            files_to_download[file_name] = file["url"]
            new_value.append(
                DatabaseExportSerializedStructure.file_field_value(
                    name=file_name,
                    visible_name=file["filename"],
                    original_name=file["filename"],
                )
            )

        return new_value


class SelectAirtableColumnType(AirtableColumnType):
    type = "select"

    def to_baserow_export_serialized_value(
        self,
        row_id_mapping: Dict[str, Dict[str, int]],
        table: dict,
        raw_airtable_row: dict,
        raw_airtable_column: dict,
        baserow_field: Field,
        value: Any,
        files_to_download: Dict[str, str],
        config: AirtableImportConfig,
        import_report: AirtableImportReport,
    ):
        # use field id and option id for uniqueness
        return f"{raw_airtable_column.get('id')}_{value}"

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        field = SingleSelectField()
        field = set_select_options_on_field(
            field,
            raw_airtable_column.get("id", ""),
            raw_airtable_column.get("typeOptions", {}),
        )
        return field


class MultiSelectAirtableColumnType(AirtableColumnType):
    type = "multiSelect"

    def to_baserow_export_serialized_value(
        self,
        row_id_mapping: Dict[str, Dict[str, int]],
        table: dict,
        raw_airtable_row: dict,
        raw_airtable_column: dict,
        baserow_field: Field,
        value: Any,
        files_to_download: Dict[str, str],
        config: AirtableImportConfig,
        import_report: AirtableImportReport,
    ):
        # use field id and option id for uniqueness
        column_id = raw_airtable_column.get("id")
        return [f"{column_id}_{val}" for val in value]

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        field = MultipleSelectField()
        field = set_select_options_on_field(
            field,
            raw_airtable_column.get("id", ""),
            raw_airtable_column.get("typeOptions", {}),
        )
        return field


class PhoneAirtableColumnType(AirtableColumnType):
    type = "phone"

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        return PhoneNumberField()

    def to_baserow_export_serialized_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_row,
        raw_airtable_column,
        baserow_field,
        value,
        files_to_download,
        config,
        import_report,
    ):
        try:
            field_type = field_type_registry.get_by_model(baserow_field)
            field_type.validator(value)
            return value
        except ValidationError:
            row_name = get_airtable_row_primary_value(
                raw_airtable_table, raw_airtable_row
            )
            import_report.add_failed(
                f"Row: \"{row_name}\", field: \"{raw_airtable_column['name']}\"",
                SCOPE_CELL,
                raw_airtable_table["name"],
                ERROR_TYPE_DATA_TYPE_MISMATCH,
                f'Cell value "{value}" was left empty because it didn\'t pass the phone number validation.',
            )
            return ""


class CountAirtableColumnType(AirtableColumnType):
    type = "count"

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        type_options = raw_airtable_column.get("typeOptions", {})
        return CountField(through_field_id=type_options.get("relationColumnId"))

    def to_baserow_export_serialized_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_row,
        raw_airtable_column,
        baserow_field,
        value,
        files_to_download,
        config,
        import_report,
    ):
        return None
