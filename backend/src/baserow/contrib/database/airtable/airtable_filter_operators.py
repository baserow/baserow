from baserow.contrib.database.views.registries import view_filter_type_registry
from baserow.core.utils import get_value_at_path

from .exceptions import AirtableSkipFilter
from .helpers import to_import_select_option_id
from .registry import AirtableFilterOperator
from .utils import (
    airtable_date_filter_value_to_baserow,
    skip_filter_if_type_duration_and_value_too_high,
)


class AirtableContainsOperator(AirtableFilterOperator):
    type = "contains"

    def to_baserow_filter_and_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        if raw_airtable_column["type"] in ["foreignKey"]:
            return view_filter_type_registry.get("link_row_contains"), value

        return view_filter_type_registry.get("contains"), value


class AirtableDoesNotContainOperator(AirtableFilterOperator):
    type = "doesNotContain"

    def to_baserow_filter_and_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        if raw_airtable_column["type"] in ["foreignKey"]:
            return view_filter_type_registry.get("link_row_not_contains"), value

        if raw_airtable_column["type"] in ["multiSelect"]:
            if not value:
                value = []
            value = [f"{raw_airtable_column['id']}_{v}" for v in value]
            value = ",".join(value)
            return view_filter_type_registry.get("multiple_select_has_not"), value

        return view_filter_type_registry.get("contains_not"), value


class AirtableEqualOperator(AirtableFilterOperator):
    type = "="

    def to_baserow_filter_and_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        if raw_airtable_column["type"] in [
            "text",
            "multilineText",
            "number",
            "rating",
            "phone",
            "autoNumber",
        ]:
            skip_filter_if_type_duration_and_value_too_high(raw_airtable_column, value)
            return view_filter_type_registry.get("equal"), str(value)

        if raw_airtable_column["type"] in ["checkbox"]:
            return (
                view_filter_type_registry.get("boolean"),
                "true" if value else "false",
            )

        if raw_airtable_column["type"] in ["select"]:
            value = to_import_select_option_id(raw_airtable_column["id"], value)
            return view_filter_type_registry.get("single_select_equal"), value

        if raw_airtable_column["type"] in ["multiSelect"]:
            if not value:
                value = []
            value = [f"{raw_airtable_column['id']}_{v}" for v in value]
            value = ",".join(value)
            return view_filter_type_registry.get("multiple_select_has"), value

        if raw_airtable_column["type"] in ["collaborator"]:
            return view_filter_type_registry.get("multiple_collaborators_has"), value

        if raw_airtable_column["type"] in ["date"]:
            value = airtable_date_filter_value_to_baserow(value)
            return view_filter_type_registry.get("date_is"), value

        if raw_airtable_column["type"] in ["foreignKey"]:
            if isinstance(value, list):
                if len(value) > 1:
                    raise AirtableSkipFilter
                foreign_table_id = get_value_at_path(
                    raw_airtable_column, "typeOptions.foreignTableId"
                )
                table_row_id_mapping = row_id_mapping.get(foreign_table_id, {})
                value = [
                    str(table_row_id_mapping.get(v))
                    for v in value
                    if v in table_row_id_mapping
                ]
                value = ",".join(value)
            return view_filter_type_registry.get("link_row_has"), value

        raise AirtableSkipFilter


class AirtableNotEqualOperator(AirtableFilterOperator):
    type = "!="

    def to_baserow_filter_and_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        if raw_airtable_column["type"] in [
            "text",
            "multilineText",
            "number",
            "rating",
            "phone",
            "autoNumber",
        ]:
            skip_filter_if_type_duration_and_value_too_high(raw_airtable_column, value)
            return view_filter_type_registry.get("not_equal"), str(value)

        if raw_airtable_column["type"] in ["select"]:
            value = to_import_select_option_id(raw_airtable_column["id"], value)
            return view_filter_type_registry.get("single_select_not_equal"), value

        if raw_airtable_column["type"] in ["collaborator"]:
            return (
                view_filter_type_registry.get("multiple_collaborators_has_not"),
                value,
            )

        if raw_airtable_column["type"] in ["date"]:
            value = airtable_date_filter_value_to_baserow(value)
            return view_filter_type_registry.get("date_is_not"), value

        raise AirtableSkipFilter


class AirtableIsEmptyOperator(AirtableFilterOperator):
    type = "isEmpty"

    def to_baserow_filter_and_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        return view_filter_type_registry.get("empty"), ""


class AirtableIsNotEmptyOperator(AirtableFilterOperator):
    type = "isNotEmpty"

    def to_baserow_filter_and_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        return view_filter_type_registry.get("not_empty"), ""


class AirtableFilenameOperator(AirtableFilterOperator):
    type = "filename"

    def to_baserow_filter_and_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        return view_filter_type_registry.get("filename_contains"), value


class AirtableFiletypeOperator(AirtableFilterOperator):
    type = "filetype"

    def to_baserow_filter_and_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        if value == "image":
            value = "image"
        elif value == "text":
            value = "document"
        else:
            raise AirtableSkipFilter

        return view_filter_type_registry.get("has_file_type"), value


class AirtableIsAnyOfOperator(AirtableFilterOperator):
    type = "isAnyOf"

    def to_baserow_filter_and_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        if raw_airtable_column["type"] in ["select"]:
            value = (
                [
                    to_import_select_option_id(raw_airtable_column["id"], v)
                    for v in value
                ]
                if value
                else []
            )
            value = ",".join(value)
            return view_filter_type_registry.get("single_select_is_any_of"), value

        raise AirtableSkipFilter


class AirtableIsNoneOfOperator(AirtableFilterOperator):
    type = "isNoneOf"

    def to_baserow_filter_and_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        if raw_airtable_column["type"] in ["select"]:
            value = (
                [
                    to_import_select_option_id(raw_airtable_column["id"], v)
                    for v in value
                ]
                if value
                else []
            )
            value = ",".join(value)
            return view_filter_type_registry.get("single_select_is_none_of"), value

        raise AirtableSkipFilter


class AirtableHasAnyOfOperator(AirtableFilterOperator):
    type = "|"

    def to_baserow_filter_and_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        raise AirtableSkipFilter


class AirtableHasAllOfOperator(AirtableFilterOperator):
    type = "&"

    def to_baserow_filter_and_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        raise AirtableSkipFilter


class AirtableLessThanOperator(AirtableFilterOperator):
    type = "<"

    def to_baserow_filter_and_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        if raw_airtable_column["type"] in [
            "number",
            "rating",
            "autoNumber",
        ]:
            skip_filter_if_type_duration_and_value_too_high(raw_airtable_column, value)
            return view_filter_type_registry.get("lower_than"), str(value)

        if raw_airtable_column["type"] in ["date"]:
            value = airtable_date_filter_value_to_baserow(value)
            return view_filter_type_registry.get("date_is_before"), value

        raise AirtableSkipFilter


class AirtableMoreThanOperator(AirtableFilterOperator):
    type = ">"

    def to_baserow_filter_and_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        if raw_airtable_column["type"] in [
            "number",
            "rating",
            "autoNumber",
        ]:
            skip_filter_if_type_duration_and_value_too_high(raw_airtable_column, value)
            return view_filter_type_registry.get("higher_than"), str(value)

        if raw_airtable_column["type"] in ["date"]:
            value = airtable_date_filter_value_to_baserow(value)
            return view_filter_type_registry.get("date_is_after"), value

        raise AirtableSkipFilter


class AirtableLessThanOrEqualOperator(AirtableFilterOperator):
    type = "<="

    def to_baserow_filter_and_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        if raw_airtable_column["type"] in [
            "number",
            "rating",
            "autoNumber",
        ]:
            skip_filter_if_type_duration_and_value_too_high(raw_airtable_column, value)
            return view_filter_type_registry.get("lower_than_or_equal"), str(value)

        if raw_airtable_column["type"] in ["date"]:
            value = airtable_date_filter_value_to_baserow(value)
            return view_filter_type_registry.get("date_is_on_or_before"), value

        raise AirtableSkipFilter


class AirtableMoreThanOrEqualOperator(AirtableFilterOperator):
    type = ">="

    def to_baserow_filter_and_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        if raw_airtable_column["type"] in [
            "number",
            "rating",
            "autoNumber",
        ]:
            skip_filter_if_type_duration_and_value_too_high(raw_airtable_column, value)
            return view_filter_type_registry.get("higher_than_or_equal"), str(value)

        if raw_airtable_column["type"] in ["date"]:
            value = airtable_date_filter_value_to_baserow(value)
            return view_filter_type_registry.get("date_is_on_or_after"), value

        raise AirtableSkipFilter


class AirtableIsWithinOperator(AirtableFilterOperator):
    type = "isWithin"

    def to_baserow_filter_and_value(
        self,
        row_id_mapping,
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        if raw_airtable_column["type"] in ["date"]:
            value = airtable_date_filter_value_to_baserow(value)
            return view_filter_type_registry.get("date_is_within"), value

        raise AirtableSkipFilter
