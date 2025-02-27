from baserow.contrib.database.views.view_filters import (
    ContainsViewFilterType,
    EmptyViewFilterType,
    NotEqualViewFilterType,
)

from .registry import AirtableFilterOperator


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
        return ContainsViewFilterType, value


class AirtableDoesNotContainOperator(AirtableFilterOperator):
    type = "doesNotContain"


class AirtableEqualOperator(AirtableFilterOperator):
    type = "="


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
        return NotEqualViewFilterType, ""


class AirtableIsEmptyOperator(AirtableFilterOperator):
    type = "isEmpty"


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
        return EmptyViewFilterType, ""


class AirtableFilenameOperator(AirtableFilterOperator):
    type = "filename"


class AirtableFiletypeOperator(AirtableFilterOperator):
    type = "filetype"


class AirtableIsAnyOfOperator(AirtableFilterOperator):
    type = "isAnyOf"


class AirtableIsNoneOfOperator(AirtableFilterOperator):
    type = "isNoneOf"


class AirtableHasAnyOfOperator(AirtableFilterOperator):
    type = "|"


class AirtableHasAllOfOperator(AirtableFilterOperator):
    type = "&"


class AirtableLessThanOperator(AirtableFilterOperator):
    type = "<"


class AirtableMoreThanOperator(AirtableFilterOperator):
    type = ">"


class AirtableLessThanOrEqualOperator(AirtableFilterOperator):
    type = "<="


class AirtableMoreThanOrEqualOperator(AirtableFilterOperator):
    type = ">="


class AirtableIsWithinOperator(AirtableFilterOperator):
    type = "isWithin"
