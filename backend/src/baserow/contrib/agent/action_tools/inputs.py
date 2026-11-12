"""The editable input contract shared by the editor and callable tools."""

import re
from typing import Annotated
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email

from pydantic import (
    AfterValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    create_model,
)
from rest_framework.exceptions import ValidationError

NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
INPUT_TYPES = ("string", "email", "number", "boolean")


def validate_name(name):
    if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
        raise ValidationError(
            "Use up to 64 letters, numbers and underscores, starting with a letter "
            "or underscore.",
            code="invalid",
        )
    return name


def validate_inputs(inputs):
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


def build_input_model(inputs):
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
        "number": Annotated[float, Field(strict=True, allow_inf_nan=False)],
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
