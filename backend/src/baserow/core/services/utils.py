from enum import Enum
from typing import Any


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


def sample_data_skeleton(value: Any) -> Any:
    """
    Returns the shape of a sample value without any of its content: the same
    keys and value types, with strings as `""`, numbers as `0` and booleans as
    `False`. A list becomes a single item which merges the keys of all of its
    items, so that a schema built from the skeleton still lists every property.

    :param value: The sample value to empty.
    :return: The skeleton of the value.
    """

    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return 0
    if isinstance(value, str):
        return ""
    if isinstance(value, dict):
        return {key: sample_data_skeleton(item) for key, item in value.items()}
    if isinstance(value, list):
        if not value:
            return []
        merged = sample_data_skeleton(value[0])
        for item in value[1:]:
            merged = _merge_skeletons(merged, sample_data_skeleton(item))
        return [merged]
    return None


def _merge_skeletons(first: Any, second: Any) -> Any:
    """
    Merges two skeletons, keeping the keys of both. Where they disagree on a
    value, the first one that isn't `None` wins.
    """

    if isinstance(first, dict) and isinstance(second, dict):
        merged = dict(first)
        for key, value in second.items():
            merged[key] = (
                _merge_skeletons(merged[key], value) if key in merged else value
            )
        return merged
    if isinstance(first, list) and isinstance(second, list):
        if not first or not second:
            return first or second
        return [_merge_skeletons(first[0], second[0])]
    return second if first is None else first
