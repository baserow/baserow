from enum import Enum


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
