from baserow.contrib.database.views.registries import view_filter_type_registry

from .exceptions import AirtableSkipFilter
from .registry import AirtableFilterOperator
from .utils import airtable_date_filter_value_to_baserow


class AirtableContainsOperator(AirtableFilterOperator):
    type = "contains"

    def to_baserow_filter_and_value(
        self,
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
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        if raw_airtable_column["type"] in ["foreignKey"]:
            return view_filter_type_registry.get("link_row_not_contains"), value

        if raw_airtable_column["type"] in ["multiSelect"]:
            value = ",".join(value)
            return view_filter_type_registry.get("multiple_select_has_not"), value

        return view_filter_type_registry.get("contains_not"), value


class AirtableEqualOperator(AirtableFilterOperator):
    type = "="

    def to_baserow_filter_and_value(
        self,
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
            return view_filter_type_registry.get("equal"), str(value)

        if raw_airtable_column["type"] in ["checkbox"]:
            return (
                view_filter_type_registry.get("boolean"),
                "true" if value else "false",
            )

        if raw_airtable_column["type"] in ["select"]:
            return view_filter_type_registry.get("single_select_equal"), value

        if raw_airtable_column["type"] in ["multiSelect"]:
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
                value = ",".join(value)
            return view_filter_type_registry.get("link_row_has"), value

        raise AirtableSkipFilter


class AirtableNotEqualOperator(AirtableFilterOperator):
    type = "!="

    def to_baserow_filter_and_value(
        self,
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
            return view_filter_type_registry.get("not_equal"), str(value)

        if raw_airtable_column["type"] in ["select"]:
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
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        if raw_airtable_column["type"] in ["select"]:
            value = ",".join(value)
            return view_filter_type_registry.get("single_select_is_any_of"), value

        raise AirtableSkipFilter


class AirtableIsNoneOfOperator(AirtableFilterOperator):
    type = "isNoneOf"

    def to_baserow_filter_and_value(
        self,
        raw_airtable_table,
        raw_airtable_column,
        baserow_field,
        import_report,
        value,
    ):
        if raw_airtable_column["type"] in ["select"]:
            value = ",".join(value)
            return view_filter_type_registry.get("single_select_is_none_of"), value

        raise AirtableSkipFilter


class AirtableHasAnyOfOperator(AirtableFilterOperator):
    type = "|"

    def to_baserow_filter_and_value(
        self,
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
            return view_filter_type_registry.get("lower_than"), str(value)

        if raw_airtable_column["type"] in ["date"]:
            value = airtable_date_filter_value_to_baserow(value)
            return view_filter_type_registry.get("date_is_before"), value

        raise AirtableSkipFilter


class AirtableMoreThanOperator(AirtableFilterOperator):
    type = ">"

    def to_baserow_filter_and_value(
        self,
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
            return view_filter_type_registry.get("higher_than"), str(value)

        if raw_airtable_column["type"] in ["date"]:
            value = airtable_date_filter_value_to_baserow(value)
            return view_filter_type_registry.get("date_is_after"), value

        raise AirtableSkipFilter


class AirtableLessThanOrEqualOperator(AirtableFilterOperator):
    type = "<="

    def to_baserow_filter_and_value(
        self,
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
            return view_filter_type_registry.get("lower_than_or_equal"), str(value)

        if raw_airtable_column["type"] in ["date"]:
            value = airtable_date_filter_value_to_baserow(value)
            return view_filter_type_registry.get("date_is_on_or_before"), value

        raise AirtableSkipFilter


class AirtableMoreThanOrEqualOperator(AirtableFilterOperator):
    type = ">="

    def to_baserow_filter_and_value(
        self,
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
            return view_filter_type_registry.get("higher_than_or_equal"), str(value)

        if raw_airtable_column["type"] in ["date"]:
            value = airtable_date_filter_value_to_baserow(value)
            return view_filter_type_registry.get("date_is_on_or_after"), value

        raise AirtableSkipFilter


class AirtableIsWithinOperator(AirtableFilterOperator):
    type = "isWithin"

    def to_baserow_filter_and_value(
        self,
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
