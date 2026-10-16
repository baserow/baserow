from rest_framework.exceptions import ValidationError

AGENT_TEXT_MAX_LENGTH = 100000


def validate_configuration_values(values: dict) -> None:
    """Allow incomplete drafts while rejecting invalid types or oversized fields."""

    for field, value in values.items():
        if field in ("provider_type", "model_identifier") and value is None:
            continue
        if not isinstance(value, str):
            raise ValidationError({field: "A valid string is required."})
        if field == "name" and not value.strip():
            raise ValidationError({field: "This field may not be blank."})
        limit = (
            AGENT_TEXT_MAX_LENGTH
            if field == "instructions"
            else 160
            if field == "name"
            else 255
        )
        if len(value) > limit:
            raise ValidationError(
                {field: f"This field may not exceed {limit} characters."}
            )
