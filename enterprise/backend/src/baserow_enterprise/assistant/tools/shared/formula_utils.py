from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Callable

import udspy
from pydantic import ConfigDict

from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_ADVANCED,
    BaserowFormulaObject,
    FormulaContext,
)
from baserow.core.utils import to_path

if TYPE_CHECKING:
    pass


# =============================================================================
# Formula Marker Constants and Helpers
# =============================================================================

FORMULA_MARKER = "$formula:"


def is_formula_description(value: str) -> bool:
    """
    Check if a value is a formula description (needs LLM generation)
    vs a static string.

    :param value: The string value to check.
    :return: True if the value starts with the formula marker, indicating
        it's a description that needs formula generation.
    """
    return isinstance(value, str) and value.startswith(FORMULA_MARKER)


def get_formula_description(value: str) -> str:
    """
    Extract the description part after the formula marker.

    :param value: A string starting with FORMULA_MARKER.
    :return: The description text after the marker, stripped of whitespace.
    """
    return value[len(FORMULA_MARKER) :].strip()


def wrap_static_string(value: str) -> str:
    """
    Wrap a static string as a Baserow formula literal.

    :param value: Plain text string.
    :return: Formula-compatible string literal with proper escaping.
    """
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
        "single_select": lambda meta: {"select_options": meta.get("select_options", [])},
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
        "string": "text",
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


# =============================================================================
# Formula Generator Factory
# =============================================================================


def get_formula_generator(
    prompt: str,
    context_class: type[BaseFormulaContext] | None = None,
) -> Callable[[dict, BaseFormulaContext, int], dict[str, str]]:
    """
    Factory to create a formula generator with a custom prompt.

    :param prompt: The system prompt for the LLM describing available functions.
    :param context_class: Optional context class for type checking (unused currently).
    :return: A function that generates formulas from field descriptions.
    """

    class RuntimeFormulaGenerator(udspy.Signature):
        __doc__ = prompt

        fields_to_resolve: dict[str, Any] = udspy.InputField(
            desc=(
                "The fields that need formulas to be generated. "
                "If prefixed with [optional], the field is not mandatory."
            )
        )
        context: dict[str, Any] = udspy.InputField(
            desc="The available context to use in formula generation."
        )
        context_metadata: dict[str, Any] = udspy.InputField(
            desc="Metadata about the context fields, with refs and names to assist in formula generation."
        )
        feedback: str = udspy.InputField(
            desc="Validation errors from previous attempt. Empty if first attempt."
        )
        generated_formulas: dict[str, Any] = udspy.OutputField()

        model_config = ConfigDict(arbitrary_types_allowed=True)

    def check_formula(generated_formula: str, context: BaseFormulaContext) -> str:
        """Validate a generated formula against the context."""
        try:
            resolve_formula(
                BaserowFormulaObject.create(
                    formula=generated_formula, mode=BASEROW_FORMULA_MODE_ADVANCED
                ),
                formula_runtime_function_registry,
                context,
            )
        except Exception as exc:
            raise ValueError(f"Generated formula is invalid: {str(exc)}")
        return "ok, the formula is valid"

    def generate_formulas(
        fields_to_resolve: dict,
        context: BaseFormulaContext,
        max_retries: int = 3,
    ) -> dict[str, str]:
        """
        Generate formulas for the given field descriptions.

        :param fields_to_resolve: Dict mapping field names to descriptions.
        :param context: Formula context with available data.
        :param max_retries: Number of retry attempts on validation failure.
        :return: Dict mapping field names to generated formulas.
        :raises ValueError: If no valid formulas could be generated.
        """
        predict = udspy.Predict(RuntimeFormulaGenerator)
        feedback = ""
        valid_formulas = {}

        for __ in range(max_retries):
            result = predict(
                fields_to_resolve=fields_to_resolve,
                context=context.get_formula_context(),
                context_metadata=context.get_context_metadata(),
                feedback=feedback,
            )

            # Validate all generated formulas
            valid_formulas = {}
            generated_formulas = result.generated_formulas
            for field_id, formula in generated_formulas.items():
                try:
                    check_formula(formula, context)
                    valid_formulas[field_id] = formula
                except ValueError as exc:
                    feedback += (
                        f"Error for {field_id}, formula {formula} not valid: "
                        f"{str(exc)}\n"
                    )

            if len(valid_formulas) == len(generated_formulas):
                return valid_formulas

        # Return any valid formulas we have, or raise if none
        if valid_formulas:
            return valid_formulas
        else:
            raise ValueError(
                f"Failed to generate any valid formulas after "
                f"{max_retries} attempts. Feedback:\n{feedback}"
            )

    return generate_formulas
