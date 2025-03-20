class AirtableBaseNotPublic(Exception):
    """Raised when the Airtable base is not publicly shared."""


class AirtableBaseRequiresAuthentication(Exception):
    """Raised when the Airtable base is not publicly shared."""


class AirtableShareIsNotABase(Exception):
    """Raised when shared Airtable link is not a base."""


class AirtableImportNotRespectingConfig(Exception):
    """Raised when the Airtable import is not respecting the `AirtableImportConfig`."""


class AirtableSkipCellValue(Exception):
    """
    Raised when an Airtable cell value must be skipped, and be omitted from the
    export.
    """


class AirtableSkipFilter(Exception):
    """
    Raised when an Airtable filter is not compatible and must be skipped.
    """
