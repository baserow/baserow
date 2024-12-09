from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

from baserow.contrib.builder.pages.constants import (
    PAGE_PATH_PARAM_PREFIX,
    PATH_PARAM_EXACT_MATCH_REGEX,
    QUERY_PARAM_EXACT_MATCH_REGEX,
)


def path_validation(value: str):
    """
    Verifies that a path is semantically valid.

    :param value: The path that needs to be validated
    :raises ValidationError: If the path is not valid
    """

    if not value.startswith("/"):
        raise ValidationError("A path must start with a '/'")

    # We need to construct a full path for the URL validator to properly check if the
    # path is valid
    full_path = f"https://placeholder.com{value}"

    validator = URLValidator(message=f"The path {value} is semantically invalid")

    validator(full_path)


def path_param_name_validation(value: str):
    """
    Verifies that the path param is semantically valid.

    :param value: The path param to check
    :raises ValidationError: If the path param is not semantically valid
    """

    full_path_param = f"{PAGE_PATH_PARAM_PREFIX}{value}"

    if not PATH_PARAM_EXACT_MATCH_REGEX.match(full_path_param):
        raise ValidationError(f"Path param {value} contains invalid characters")


def query_param_name_validation(value: str):
    """
    Verifies that the path param is semantically valid.

    :param value: The path param to check
    :raises ValidationError: If the path param is not semantically valid
    """

    if not QUERY_PARAM_EXACT_MATCH_REGEX.match(value):
        raise ValidationError(f"Query param {value} contains invalid characters")
