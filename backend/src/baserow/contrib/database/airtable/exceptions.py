class AirtableBaseNotPublic(Exception):
    """Raised when the Airtable base is not publicly shared."""


class AirtableShareIsNotABase(Exception):
    """Raised when shared Airtable link is not a base."""


class AirtableImportNotRespectingConfig(Exception):
    """Raised when the Airtable import is not respecting the `AirtableImportConfig`."""
