import re
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any

from baserow.core.formula.types import FormulaContext
from baserow.core.utils import to_path

# =============================================================================
# Formula Detection Constants and Helpers
# =============================================================================

FORMULA_PREFIX = "$formula:"

# Detects raw formula syntax the LLM might write instead of using $formula:.
# Matches: get('...'), concat(...), {{ ... }}, comparison operators, if(...),
# today(), now().
RAW_FORMULA_RE = re.compile(
    r"\bget\s*\(|\bconcat\s*\(|\{\{.*\}\}"
    r"|\b(?:equal|not_equal|greater_than|less_than"
    r"|greater_than_(?:or_)?equal|less_than_(?:or_)?equal)\s*\("
    r"|\bif\s*\(|\btoday\s*\(|\bnow\s*\("
)


def needs_formula(value: str | None) -> bool:
    """
    Check if a value requires formula processing.

    Returns True for explicit ``$formula:`` prefixed values *and* for raw
    formula expressions the LLM may write inline (e.g. ``get('field')``
    or ``{{ get('field') }}``).

    :param value: The string value to check, or None.
    :return: True if the value needs formula generation.
    """

    if not value:
        return False
    stripped = value.strip()
    return stripped.lower().startswith(FORMULA_PREFIX) or bool(
        RAW_FORMULA_RE.search(stripped)
    )


def formula_desc(value: str) -> str:
    """
    Extract the formula description from a value.

    For ``$formula:`` prefixed values, strips the prefix.
    For raw formula expressions, returns the value as-is so the
    formula generator can convert it to a proper formula.

    :param value: A string containing a formula description or raw formula.
    :return: The description text or raw formula expression.
    """

    stripped = value.strip()
    if stripped.lower().startswith(FORMULA_PREFIX):
        return stripped[len(FORMULA_PREFIX) :].strip()
    # Raw formula expression — pass through for the generator to fix up
    return stripped


def literal_or_placeholder(value: str | None) -> str:
    """
    Return a quoted literal formula, or empty placeholder for formula values.

    Used when creating ORM objects: formula fields get a ``''`` placeholder
    that will be replaced later by the formula generator, while literal
    values are wrapped in single quotes.

    :param value: The string value, or None.
    :return: A single-quoted formula literal or ``''`` placeholder.
    """

    if not value or needs_formula(value):
        return "''"
    return wrap_static_string(value)


def wrap_static_string(value: str) -> str:
    """
    Wrap a static string as a Baserow formula literal.

    If the value is already a quoted formula literal (e.g. ``'Submit'``),
    it is returned unchanged to avoid double-wrapping which would produce
    escaped quotes visible in the UI (e.g. ``'\\'Submit\\''``).

    :param value: Plain text string or already-quoted formula literal.
    :return: Formula-compatible string literal with proper escaping.
    """

    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value
    escaped = value.replace("'", "\\'")
    return f"'{escaped}'"


# =============================================================================
# JSON Schema Utilities
# =============================================================================


def minimize_json_schema(schema: dict) -> dict[str, dict[str, str]]:
    """
    Generate a mapping between field ids and names/types from a JSON schema.
    Useful when generating formulas to understand the provided context.

    :param schema: JSON schema dict with properties and metadata.
    :return: Mapping of field_key -> {id, name, type, desc, ...}.
    """
    field_type_descriptions = {
        "link_row": "the row ID as number or the primary field value as string",
        "single_select": "the option ID as number or the value as string",
        "multiple_select": "a comma separated list of option IDs or values as string",
        "date": "a date string in ISO 8601 format",
        "date_time": "a date-time string in ISO 8601 format",
        "boolean": "true or false",
    }
    field_type_extra_info = {
        "single_select": lambda meta: {
            "select_options": meta.get("select_options", [])
        },
        "multiple_select": lambda meta: {
            "select_options": meta.get("select_options", [])
        },
        "multiple_collaborators": lambda meta: {
            "available_collaborators": meta.get("available_collaborators", [])
        },
    }

    if schema.get("type") == "array":
        return minimize_json_schema(schema.get("items"))
    elif schema.get("type") != "object":
        raise ValueError("Schema must be of type object or array of objects")

    properties = schema.get("properties", {})
    mapping = {}
    for key, prop in properties.items():
        metadata = prop.get("metadata")
        if metadata:
            field_type = metadata["type"]
            mapping[key] = {
                "id": metadata["id"],
                "name": metadata["name"],
                "type": field_type,
                "desc": field_type_descriptions.get(field_type, ""),
            }
            if field_type in field_type_extra_info:
                get_extra_info = field_type_extra_info[field_type]
                mapping[key].update(get_extra_info(metadata))
    return mapping


def create_example_from_json_schema(schema: dict) -> Any:
    """
    Generate example data from a JSON schema.
    Useful when generating formulas to provide example context data.

    :param schema: JSON schema dict.
    :return: Example data matching the schema structure.
    """
    examples = {
        "string": "1",
        "number": 1,
        "boolean": True,
        "null": None,
        "object": lambda prop: create_example_from_json_schema(prop),
        "array": lambda prop: [create_example_from_json_schema(prop["items"])],
    }

    if schema.get("type") == "array":
        return [create_example_from_json_schema(schema.get("items"))]
    elif schema.get("type") != "object":
        raise ValueError("Schema must be of type object or array of objects")

    properties = schema.get("properties", {})
    example = {}
    for key, prop in properties.items():
        value = examples[prop.get("type")]
        if callable(value):
            example[key] = value(prop)
        else:
            example[key] = value
    return example


# =============================================================================
# Base Formula Context
# =============================================================================


class BaseFormulaContext(FormulaContext, ABC):
    """
    Base context for formula generation, shared between automation and builder.

    Subclasses must implement get_formula_context() and __getitem__ for
    path resolution.
    """

    def __init__(self):
        self.context: dict[str, Any] = {}
        self.context_metadata: dict[str, Any] = {}
        super().__init__()

    def add_context(
        self,
        key: str,
        example_data: Any,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Add data to the formula context.

        :param key: Context key (e.g., "data_source.5" or "1" for node ID).
        :param example_data: Example data for this context entry.
        :param metadata: Optional metadata describing the structure.
        """
        self.context[key] = example_data
        if metadata:
            self.context_metadata[key] = metadata

    @abstractmethod
    def get_formula_context(self) -> dict[str, Any]:
        """Return the context dict for formula generation."""
        pass

    def get_context_metadata(self) -> dict[str, Any]:
        """Return metadata about the context."""
        return self.context_metadata

    def _resolve_path(self, key: str, root_key: str) -> Any:
        """
        Resolve a dotted path through the context.

        :param key: Full path like "data_source.5.field_name".
        :param root_key: Expected root key to validate against.
        :return: The resolved value.
        :raises KeyError: If path cannot be resolved.
        :raises ValueError: If resolved value is not a primitive type.
        """
        start, *key_parts = to_path(key)
        if start != root_key:
            raise KeyError(
                f"Key '{key}' not found in context. "
                f"Only '{root_key}' is supported at the root level."
            )

        value = self.context
        for kp in key_parts:
            try:
                value = value[int(kp) if isinstance(value, list) else kp]
            except (KeyError, TypeError, ValueError):
                available_keys = (
                    list(value.keys())
                    if isinstance(value, dict)
                    else ", ".join(map(str, range(len(value))))
                )
                raise KeyError(
                    f"Key '{kp}' of '{key}' not found in {value}, "
                    f"Available keys: {available_keys}"
                )

        if not isinstance(value, (int, float, str, bool, date, datetime)):
            raise ValueError(
                f"Value for key '{key}' is not a valid type. "
                f"Expected int, float, str, bool, date, or datetime. "
                f"Got {type(value).__name__} instead. "
                f"Make sure to only reference primitive types in the formula context."
            )
        return value
