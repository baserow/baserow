from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict

from django.core.exceptions import ValidationError

from baserow.contrib.database.export_serialized import DatabaseExportSerializedStructure
from baserow.contrib.database.fields.models import (
    NUMBER_MAX_DECIMAL_PLACES,
    AutonumberField,
    BooleanField,
    CountField,
    CreatedOnField,
    DateField,
    DurationField,
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
from baserow.contrib.database.fields.utils.duration import D_H, H_M_S_SSS

from .config import AirtableImportConfig
from .constants import (
    AIRTABLE_DOWNLOAD_FILE_TYPE_FETCH,
    AIRTABLE_DURATION_FIELD_DURATION_FORMAT_MAPPING,
    AIRTABLE_MAX_DURATION_VALUE,
    AIRTABLE_NUMBER_FIELD_SEPARATOR_FORMAT_MAPPING,
    AIRTABLE_RATING_COLOR_MAPPING,
    AIRTABLE_RATING_ICON_MAPPING,
)
from .exceptions import AirtableSkipCellValue
from .helpers import (
    import_airtable_date_type_options,
    set_select_options_on_field,
    to_import_select_option_id,
)
from .import_report import (
    ERROR_TYPE_DATA_TYPE_MISMATCH,
    ERROR_TYPE_UNSUPPORTED_FEATURE,
    SCOPE_CELL,
    SCOPE_FIELD,
    AirtableImportReport,
)
from .models import DownloadFile
from .registry import AirtableColumnType
from .utils import get_airtable_row_primary_value, quill_to_markdown


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
            return TextField(text_default=raw_airtable_column.get("default", ""))

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

    def to_baserow_export_empty_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_row,
        raw_airtable_column,
        baserow_field,
        files_to_download,
        config,
        import_report,
    ):
        # If the `text_default` is set, then we must return an empty string. If we
        # don't, the value is omitted in the export, resulting in the default value
        # automatically being set, while it's actually empty in Airtable.
        if isinstance(baserow_field, TextField) and baserow_field.text_default != "":
            return ""
        else:
            raise AirtableSkipCellValue


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
        return LongTextField(long_text_enable_rich_text=True)

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
        return quill_to_markdown(value["documentValue"])


class NumberAirtableColumnType(AirtableColumnType):
    type = "number"

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        default_value = raw_airtable_column.get("default")
        type_options = raw_airtable_column.get("typeOptions", {})
        options_format = type_options.get("format", "")

        if options_format in ["duration", "durationInDays"]:
            return self.to_duration_field(
                raw_airtable_table, raw_airtable_column, config, import_report
            )
        else:
            field = self.to_number_field(
                raw_airtable_table, raw_airtable_column, config, import_report
            )
            if default_value is not None:
                if "percent" in options_format:
                    default_value = default_value * 100
                field.number_default = default_value
            return field

    def to_duration_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        type_options = raw_airtable_column.get("typeOptions", {})
        options_format = type_options.get("format", "")
        duration_format = type_options.get("durationFormat", "")

        if options_format == "durationInDays":
            # It looks like this option is broken in Airtable. When this is selected,
            # the exact value seems to be in seconds, but it should be in days. We
            # will therefore convert it to days when calculating the value.
            duration_format = D_H
        else:
            # Fallback to the most specific format because that leaves most of the
            # value intact.
            duration_format = AIRTABLE_DURATION_FIELD_DURATION_FORMAT_MAPPING.get(
                duration_format, H_M_S_SSS
            )

        return DurationField(duration_format=duration_format)

    def to_number_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        suffix = ""

        type_options = raw_airtable_column.get("typeOptions", {})
        options_format = type_options.get("format", "")

        if "percent" in options_format:
            suffix = "%"

        decimal_places = min(
            max(0, type_options.get("precision", 0)), NUMBER_MAX_DECIMAL_PLACES
        )
        prefix = type_options.get("symbol", "")
        separator_format = type_options.get("separatorFormat", "")
        number_separator = AIRTABLE_NUMBER_FIELD_SEPARATOR_FORMAT_MAPPING.get(
            separator_format, ""
        )

        if separator_format != "" and number_separator == "":
            import_report.add_failed(
                raw_airtable_column["name"],
                SCOPE_FIELD,
                raw_airtable_table.get("name", ""),
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                f"The field was imported, but the separator format "
                f"{separator_format} was dropped because it doesn't exist in Baserow.",
            )
        default_value = raw_airtable_column.get("default", "") or None

        return NumberField(
            number_decimal_places=decimal_places,
            number_negative=type_options.get("negative", True),
            number_prefix=prefix,
            number_suffix=suffix,
            number_separator=number_separator,
            number_default=default_value,
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
            return None

        type_options = raw_airtable_column.get("typeOptions", {})
        options_format = type_options.get("format", "")
        row_name = get_airtable_row_primary_value(raw_airtable_table, raw_airtable_row)

        if options_format == "durationInDays":
            # If the formatting is in days, we must multiply the raw value in seconds
            # by the number of seconds in a day.
            value = value * 60 * 60 * 24

        if "duration" in options_format:
            # If the value is higher than the maximum that the `timedelta` can handle,
            # then we can't use it, so we have to drop it. The maximum number of days
            # in `timedelta` is `999999999`, so the max number of seconds are
            # 999999999 * 24 * 60 * 60 = 86399999913600.
            if abs(value) > AIRTABLE_MAX_DURATION_VALUE:
                import_report.add_failed(
                    f"Row: \"{row_name}\", field: \"{raw_airtable_column['name']}\"",
                    SCOPE_CELL,
                    raw_airtable_table["name"],
                    ERROR_TYPE_DATA_TYPE_MISMATCH,
                    f"Cell value was left empty because the duration seconds {value} "
                    f'is outside the -86399999913600 and 86399999913600 range."',
                )
                return None

            # If the value is a duration, then we can use the same value because both
            # store it as seconds.
            return value

        try:
            value = Decimal(value)
        except InvalidOperation:
            # If the value can't be parsed as decimal, then it might be corrupt, so we
            # need to inform the user and skip the import.
            import_report.add_failed(
                f"Row: \"{row_name}\", field: \"{raw_airtable_column['name']}\"",
                SCOPE_CELL,
                raw_airtable_table["name"],
                ERROR_TYPE_DATA_TYPE_MISMATCH,
                f"Cell value was left empty because the numeric value {value} "
                f'could not be parsed"',
            )
            return None

        # Airtable stores 10% as 0.1, so we would need to multiply it by 100 so get the
        # correct value in Baserow.
        if "percent" in options_format:
            value = value * 100

        if not baserow_field.number_negative and value < 0:
            return None

        return str(value)

    def to_baserow_export_empty_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_row,
        raw_airtable_column,
        baserow_field,
        files_to_download,
        config,
        import_report,
    ):
        # If the field has a default value, we need to explicitly return None
        # to ensure that empty values in Airtable are properly imported as empty in
        # Baserow. Otherwise, the value would be omitted in the export, resulting in
        # the default value automatically being set, while it's actually empty in
        # Airtable.
        # Default value can be set only on NumberField
        if (
            isinstance(baserow_field, NumberField)
            and baserow_field.number_default is not None
        ):
            return None
        else:
            raise AirtableSkipCellValue


class RatingAirtableColumnType(AirtableColumnType):
    type = "rating"

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        type_options = raw_airtable_column.get("typeOptions", {})
        airtable_icon = type_options.get("icon", "")
        airtable_max = type_options.get("max", 5)
        airtable_color = type_options.get("color", "")

        style = AIRTABLE_RATING_ICON_MAPPING.get(airtable_icon, "")
        if style == "":
            style = list(AIRTABLE_RATING_ICON_MAPPING.values())[0]
            import_report.add_failed(
                raw_airtable_column["name"],
                SCOPE_FIELD,
                raw_airtable_table.get("name", ""),
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                f"The field was imported, but the icon {airtable_icon} does not "
                f"exist, so it defaulted to {style}.",
            )

        color = AIRTABLE_RATING_COLOR_MAPPING.get(airtable_color, "")
        if color == "":
            color = list(AIRTABLE_RATING_COLOR_MAPPING.values())[0]
            import_report.add_failed(
                raw_airtable_column["name"],
                SCOPE_FIELD,
                raw_airtable_table.get("name", ""),
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                f"The field was imported, but the color {airtable_color} does not "
                f"exist, so it defaulted to {color}.",
            )

        return RatingField(
            max_value=airtable_max,
            style=style,
            color=color,
        )


class CheckboxAirtableColumnType(AirtableColumnType):
    type = "checkbox"

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        type_options = raw_airtable_column.get("typeOptions", {})
        airtable_icon = type_options.get("icon", "check")
        airtable_color = type_options.get("color", "green")

        if airtable_icon != "check":
            import_report.add_failed(
                raw_airtable_column["name"],
                SCOPE_FIELD,
                raw_airtable_table.get("name", ""),
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                f"The field was imported, but the icon {airtable_icon} is not supported.",
            )

        if airtable_color != "green":
            import_report.add_failed(
                raw_airtable_column["name"],
                SCOPE_FIELD,
                raw_airtable_table.get("name", ""),
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                f"The field was imported, but the color {airtable_color} is not supported.",
            )

        default = raw_airtable_column.get("default", None) or False
        return BooleanField(boolean_default=default)

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

    def to_baserow_export_empty_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_row,
        raw_airtable_column,
        baserow_field,
        files_to_download,
        config,
        import_report,
    ):
        # If the field has a default value of True, we need to explicitly return "false"
        # to ensure that empty values in Airtable are properly imported as False in
        # Baserow. Otherwise, the value would be omitted in the export, resulting in
        # the default value automatically being set, while it's actually empty in
        # Airtable.
        if baserow_field.boolean_default:
            return "false"
        else:
            raise AirtableSkipCellValue


class DateAirtableColumnType(AirtableColumnType):
    type = "date"

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        self.add_import_report_failed_if_default_is_provided(
            raw_airtable_table,
            raw_airtable_column,
            import_report,
            to_human_readable_default=lambda x: "Current date",
        )

        type_options = raw_airtable_column.get("typeOptions", {})
        # Check if a timezone is provided in the type options, if so, we might want
        # to use that timezone for the conversion later on.
        airtable_timezone = type_options.get("timeZone", None)
        date_show_tzinfo = type_options.get("shouldDisplayTimeZone", False)

        # date_force_timezone=None it the equivalent of airtable_timezone="client".
        if airtable_timezone == "client":
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

        # date_force_timezone=None it the equivalent of airtable_timezone="client".
        if airtable_timezone == "client":
            airtable_timezone = None

        # The formula conversion isn't support yet, but because the Created on and
        # Last modified fields work as a formula, we can convert those.
        if is_last_modified:
            dependencies = type_options.get("dependencies", {})
            all_column_modifications = dependencies.get(
                "dependsOnAllColumnModifications", False
            )

            if not all_column_modifications:
                import_report.add_failed(
                    raw_airtable_column["name"],
                    SCOPE_FIELD,
                    raw_airtable_table.get("name", ""),
                    ERROR_TYPE_UNSUPPORTED_FEATURE,
                    f"The field was imported, but the support to depend on "
                    f"specific fields was dropped because that's not supported by "
                    f"Baserow.",
                )

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
        relationship = type_options.get("relationship", "many")  # can be: one
        view_id_for_record_selection = type_options.get(
            "viewIdForRecordSelection", None
        )
        filters_for_record_selection = type_options.get(
            "filtersForRecordSelection", None
        )
        ai_matching_options = type_options.get("aiMatchingOptions", None)

        if relationship != "many":
            import_report.add_failed(
                raw_airtable_column["name"],
                SCOPE_FIELD,
                raw_airtable_table.get("name", ""),
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                f"The field was imported, but support for a one to many "
                f"relationship was dropped because it's not supported by Baserow.",
            )

        if view_id_for_record_selection is not None:
            import_report.add_failed(
                raw_airtable_column["name"],
                SCOPE_FIELD,
                raw_airtable_table.get("name", ""),
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                f"The field was imported, but limiting record selection to a view "
                f"was dropped because the views have not been imported.",
            )

        if filters_for_record_selection is not None:
            import_report.add_failed(
                raw_airtable_column["name"],
                SCOPE_FIELD,
                raw_airtable_table.get("name", ""),
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                f"The field was imported, but filtering record by a condition "
                f"was dropped because it's not supported by Baserow.",
            )

        if ai_matching_options is not None:
            import_report.add_failed(
                raw_airtable_column["name"],
                SCOPE_FIELD,
                raw_airtable_table.get("name", ""),
                ERROR_TYPE_UNSUPPORTED_FEATURE,
                f"The field was imported, but using AI to show top matches was "
                f"dropped because it's not supported by Baserow.",
            )

        return LinkRowField(
            link_row_table_id=foreign_table_id,
            link_row_related_field_id=type_options.get("symmetricColumnId"),
        )

    def after_field_objects_prepared(
        self, field_mapping_per_table, baserow_field, raw_airtable_column
    ):
        foreign_table_id = raw_airtable_column["typeOptions"]["foreignTableId"]
        foreign_field_mapping = field_mapping_per_table[foreign_table_id]
        foreign_primary_field = next(
            field["baserow_field"]
            for field in foreign_field_mapping.values()
            if field["baserow_field"].primary
        )
        baserow_field.link_row_table_primary_field = foreign_primary_field

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
            files_to_download[file_name] = DownloadFile(
                url=file["url"],
                row_id=raw_airtable_row["airtable_record_id"],
                column_id=raw_airtable_column["id"],
                attachment_id=file["id"],
                type=AIRTABLE_DOWNLOAD_FILE_TYPE_FETCH,
            )
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
    default_value_field = "single_select_default"

    def to_baserow_export_serialized_value(
        self,
        row_id_mapping: Dict[str, Dict[str, int]],
        table: dict,
        raw_airtable_row: dict,
        raw_airtable_column: dict,
        baserow_field: Field,
        value: Any,
        files_to_download: Dict[str, DownloadFile],
        config: AirtableImportConfig,
        import_report: AirtableImportReport,
    ):
        # use field id and option id for uniqueness
        return to_import_select_option_id(raw_airtable_column.get("id"), value)

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        id_value = raw_airtable_column.get("id", "")
        type_options = raw_airtable_column.get("typeOptions", {})

        field = SingleSelectField()
        field = set_select_options_on_field(field, id_value, type_options)

        default_value = raw_airtable_column.get("default", None)
        if default_value is not None:
            default_option = to_import_select_option_id(id_value, default_value)
            # Ensure that the default value is one of existing options
            field.single_select_default = next(
                (
                    option.id
                    for option in field._prefetched_objects_cache["select_options"]
                    if option.id == default_option
                ),
                None,
            )
        return field

    def to_baserow_export_empty_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_row,
        raw_airtable_column,
        baserow_field,
        files_to_download,
        config,
        import_report,
    ):
        if baserow_field.single_select_default is not None:
            return None
        else:
            raise AirtableSkipCellValue


class MultiSelectAirtableColumnType(AirtableColumnType):
    type = "multiSelect"
    default_value_field = "multiple_select_default"

    def to_baserow_export_serialized_value(
        self,
        row_id_mapping: Dict[str, Dict[str, int]],
        table: dict,
        raw_airtable_row: dict,
        raw_airtable_column: dict,
        baserow_field: Field,
        value: Any,
        files_to_download: Dict[str, DownloadFile],
        config: AirtableImportConfig,
        import_report: AirtableImportReport,
    ):
        # use field id and option id for uniqueness
        column_id = raw_airtable_column.get("id")
        return [to_import_select_option_id(column_id, val) for val in value]

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        id_value = raw_airtable_column.get("id", "")
        type_options = raw_airtable_column.get("typeOptions", {})

        field = MultipleSelectField()
        field = set_select_options_on_field(field, id_value, type_options)

        default_value = raw_airtable_column.get("default", None)
        if default_value:
            default_options = [
                to_import_select_option_id(id_value, val) for val in default_value
            ]
            field.multiple_select_default = [
                option.id
                for option in field._prefetched_objects_cache["select_options"]
                if option.id in default_options
            ]
        return field

    def to_baserow_export_empty_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_row,
        raw_airtable_column,
        baserow_field,
        files_to_download,
        config,
        import_report,
    ):
        if baserow_field.multiple_select_default is not None:
            return []
        else:
            raise AirtableSkipCellValue


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


class AutoNumberAirtableColumnType(AirtableColumnType):
    type = "autoNumber"

    def to_baserow_field(
        self, raw_airtable_table, raw_airtable_column, config, import_report
    ):
        return AutonumberField()
