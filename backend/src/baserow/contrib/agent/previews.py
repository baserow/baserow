"""
Readable requests of the Agent's tools: values masked and lists cut to what
people can read.
"""

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

from pydantic import BaseModel

from baserow.core.chat_runs.tool_input import tool_input_preview

MAX_PREVIEW_ITEMS = 10
MAX_PREVIEW_KEYS = 10
MASKED_VALUE = "••••"


@dataclass
class StepPreview:
    """
    A call's request as people read it: the names of what it works on, and the
    items it asks for under ``items_key``.
    """

    names: dict[str, str]
    items_key: str | None = None
    items: list[Any] = dataclass_field(default_factory=list)
    truncated: bool = False
    """Whether items or keys were left out."""

    def cut_items(self, items: list[Any]) -> list[Any]:
        """
        :param items: The requested items, before their names are resolved.
        :return: The first ``MAX_PREVIEW_ITEMS`` of them, the only ones resolved.
            The preview is marked as cut when there are more.
        """

        if len(items) > MAX_PREVIEW_ITEMS:
            self.truncated = True
        return items[:MAX_PREVIEW_ITEMS]

    def to_input(self) -> dict[str, Any]:
        """
        Bound the preview for the step's input: every list keeps its first
        ``MAX_PREVIEW_ITEMS`` items and every object its first ``MAX_PREVIEW_KEYS``
        keys, at any depth, and ``tool_input_preview`` shortens long strings. When
        the JSON is still too large to store, trailing items are left out until it
        fits, so the names always stay.

        :return: ``values``, and ``truncated`` when anything was left out.
        """

        items = cut(self.items)
        truncated = self.truncated or items != self.items
        while True:
            values: dict[str, Any] = dict(self.names)
            if self.items_key is not None:
                values[self.items_key] = items
            bounded = tool_input_preview(values)
            if bounded or not items:
                break
            items.pop()
            truncated = True
        if bounded and truncated:
            bounded["truncated"] = True
        return bounded


def cut(value: Any) -> Any:
    """
    :param value: A requested value.
    :return: The value with every list cut to its first ``MAX_PREVIEW_ITEMS`` items
        and every object to its first ``MAX_PREVIEW_KEYS`` keys, at any depth.
    """

    if isinstance(value, list):
        return [cut(item) for item in value[:MAX_PREVIEW_ITEMS]]
    if isinstance(value, dict):
        return {key: cut(item) for key, item in list(value.items())[:MAX_PREVIEW_KEYS]}
    return value


def as_requested(value: Any) -> Any:
    """
    :param value: Validated tool arguments, or one of their values.
    :return: The value as JSON, with only what the model sent: defaults it left
        out stay out.
    """

    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_unset=True)
    if isinstance(value, dict):
        return {key: as_requested(item) for key, item in value.items()}
    if isinstance(value, list):
        return [as_requested(item) for item in value]
    return value


def mask(values: dict[str, Any], readable: set[str]) -> dict[str, Any]:
    """
    Show only values whose key is exactly a readable field's name, so a
    misspelled or unknown key can never reveal a password.

    :param values: One row's values by field name.
    :param readable: The names of the table's readable fields.
    :return: The values, with every other key's value masked.
    """

    return {
        name: value if name in readable else MASKED_VALUE
        for name, value in values.items()
    }


def name_field_references(value: Any, names: dict[int, str]) -> Any:
    """
    Name the fields a view or filter refers to: ``field_id`` becomes ``field`` and
    ``<x>_field_id`` becomes ``<x>_field``. An ID that isn't a field of the table
    stays as written, so the tool's own item error explains it.

    :param value: A view or filter request, or one of its values.
    :param names: The table's field names by ID.
    :return: The request with known field IDs replaced by names.
    """

    if isinstance(value, list):
        return [name_field_references(item, names) for item in value]
    if not isinstance(value, dict):
        return value
    named: dict[str, Any] = {}
    for key, item in value.items():
        if key.endswith("field_id") and isinstance(item, int) and item in names:
            named[key.removesuffix("_id")] = names[item]
        else:
            named[key] = name_field_references(item, names)
    return named
