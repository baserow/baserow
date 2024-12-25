from django.core.exceptions import ValidationError

EMPTY_VALUES = (None, "", b"", [], (), {})


def no_empty_form_values_when_required_validator(value):
    if value_is_empty_for_required_form_field(value):
        raise ValidationError("This field is required.", code="required")


def allow_only_specific_select_options_factory(allowed_select_option_ids):
    def allow_only_specific_select_options(value):
        if not isinstance(value, list):
            value = [value]
        for v in value:
            if v not in allowed_select_option_ids:
                raise ValidationError(
                    f"The provided select option {v} is not allowed.", code="invalid"
                )

    return allow_only_specific_select_options


def value_is_empty_for_required_form_field(value):
    return value in EMPTY_VALUES or value is False
