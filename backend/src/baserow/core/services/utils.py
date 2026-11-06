from enum import Enum


def sanitize_sample_data(value):
    """Replace JSON values with placeholders, preserving keys, types and shape."""

    if isinstance(value, dict):
        return {key: sanitize_sample_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_sample_data(item) for item in value]
    if isinstance(value, str):
        return "Example"
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return 0
    if isinstance(value, float):
        return 0.0
    return None


class ServiceAdhocRefinements(Enum):
    """
    Enum class that represents the possible refinements that can be applied to adhoc
    filtering, sorting and searching of services.
    """

    FILTER = "FILTER"
    SORT = "SORT"
    SEARCH = "SEARCH"

    @classmethod
    def to_model_field(cls, refinement: "ServiceAdhocRefinements") -> str:
        value_to_model_field = {
            cls.FILTER: "filterable",
            cls.SORT: "sortable",
            cls.SEARCH: "searchable",
        }
        return value_to_model_field[refinement]
