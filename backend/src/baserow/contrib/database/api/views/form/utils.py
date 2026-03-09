from typing import Tuple

from rest_framework.fields import empty

from baserow.contrib.database.fields.models import FormViewEditRowField
from baserow.contrib.database.fields.utils.row_edit import verify_and_decode_edit_token
from baserow.contrib.database.views.models import FormView
from baserow.contrib.database.views.validators import (
    allow_only_specific_select_options_factory,
    no_empty_form_values_when_required_validator,
)

from .exceptions import InvalidEditRowTokenError


def decode_and_validate_edit_token(form: FormView, token: str) -> Tuple[int, int]:
    """
    Decode the edit token and validate it against the given form view.

    :param form: The form view the token must belong to.
    :param token: The signed edit token string.
    :raises InvalidEditRowTokenError: If the token is missing, invalid, or
        does not match the form view.
    :return: A (row_id, field_id) tuple extracted from the valid token.
    """

    if not token:
        raise InvalidEditRowTokenError()

    data = verify_and_decode_edit_token(token)
    if data is None or data.get("view_id") != form.id:
        raise InvalidEditRowTokenError()

    field_id = data.get("field_id")
    if not FormViewEditRowField.objects.filter(id=field_id, form_view=form).exists():
        raise InvalidEditRowTokenError()

    return data["row_id"], field_id


def build_field_kwargs_for_options(model, options, enforce_required=False):
    """
    Builds `field_kwargs` for the row serializer based on the form view's
    active field options.

    When *enforce_required* is ``True`` (used by the submit endpoint), fields
    marked as required will get ``required=True`` and the "not empty" validator.
    """

    field_kwargs = {}
    for option in options:
        validators = []
        o = {}
        if enforce_required and option.is_required():
            o["required"] = True
            o["default"] = empty
            validators.append(no_empty_form_values_when_required_validator)
        if not option.include_all_select_options:
            validators.append(
                allow_only_specific_select_options_factory(
                    [
                        allowed_select_option.id
                        for allowed_select_option in option.allowed_select_options.all()
                    ]
                )
            )
        if len(validators) > 0 and len(o) > 0:
            name = model._field_objects[option.field_id]["name"]
            o["validators"] = validators
            field_kwargs[name] = o
    return field_kwargs
