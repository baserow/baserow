"""The names and the editable input contract shared by the editor and callable tools."""

import re
from typing import Annotated, Any, TypedDict
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    WithJsonSchema,
    create_model,
)
from rest_framework.exceptions import ValidationError

from baserow.contrib.integrations.mcp.toolset import RESERVED_MODEL_TOOL_NAME

NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
INPUT_TYPES = ("string", "email", "number", "boolean")


class AgentActionInput(TypedDict):
    """One value the model supplies when it calls an action."""

    id: str
    """Stable UUID that formulas reference; it never changes on rename."""
    name: str
    type: str
    description: str
    required: bool


def validate_name(name: Any) -> str:
    """
    :param name: The name of an action or of one of its inputs.
    :return: The name.
    :raises ValidationError: When the model's provider wouldn't accept it.
    """

    if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
        raise ValidationError(
            "Use up to 64 letters, numbers and underscores, starting with a letter "
            "or underscore.",
            code="invalid",
        )
    return name


def validate_action_name(name: Any) -> str:
    """
    :param name: The name the model would call an action by.
    :return: The name.
    :raises ValidationError: When it's malformed, or could be the name of a
        connected app's tool.
    """

    validate_name(name)
    if RESERVED_MODEL_TOOL_NAME.match(name):
        raise ValidationError(
            'Names starting with "mcp" and a number are reserved for the tools '
            "of connected apps.",
            code="reserved",
        )
    return name


def validate_inputs(inputs: Any) -> list[AgentActionInput]:
    """Validate definitions without generating or changing their stable identities."""

    if not isinstance(inputs, list) or len(inputs) > 100:
        raise ValidationError("Provide a list of at most 100 inputs.")
    ids, names, result = set(), set(), []
    for item in inputs:
        if not isinstance(item, dict):
            raise ValidationError("Each input must be an object.")
        try:
            input_id = str(UUID(item["id"]))
            name = validate_name(item["name"])
            input_type = item["type"]
            required = item["required"]
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise ValidationError(
                "Each input needs an ID, name, type and required flag."
            ) from exc
        if input_id in ids or name in names:
            raise ValidationError("Input IDs and names must be unique.")
        if input_type not in INPUT_TYPES or not isinstance(required, bool):
            raise ValidationError("Invalid input type or required flag.")
        description = item.get("description", "")
        if not isinstance(description, str) or len(description) > 2000:
            raise ValidationError("Input descriptions must be at most 2000 characters.")
        ids.add(input_id)
        names.add(name)
        result.append(
            {
                "id": input_id,
                "name": name,
                "type": input_type,
                "description": description,
                "required": required,
            }
        )
    return result


def _validate_email(value):
    try:
        validate_email(value)
    except DjangoValidationError as exc:
        raise ValueError("Enter a valid email address.") from exc
    return value


def build_input_model(inputs: list[AgentActionInput]) -> type[BaseModel]:
    """Build one strict contract for both the advertised schema and validation.

    Internal field names avoid collisions with Pydantic methods and private fields.
    Callable names are aliases; callers serializing a model must use ``by_alias``.
    """

    input_types = {
        "string": StrictStr,
        "email": Annotated[
            StrictStr,
            AfterValidator(_validate_email),
            Field(json_schema_extra={"format": "email"}),
        ],
        "number": Annotated[
            StrictInt | Annotated[float, Field(strict=True, allow_inf_nan=False)],
            WithJsonSchema({"type": "number"}),
        ],
        "boolean": StrictBool,
    }
    fields = {}
    for index, item in enumerate(inputs):
        annotation = input_types[item["type"]]
        required = item["required"]
        if not required:
            annotation = annotation | None
        fields[f"input_{index}"] = (
            annotation,
            Field(
                default=... if required else None,
                alias=item["name"],
                description=item["description"],
            ),
        )
    return create_model("ActionInputs", __config__=ConfigDict(extra="forbid"), **fields)
