from django.core.exceptions import ValidationError

from rest_framework.exceptions import APIException

from baserow.api.exceptions import RequestBodyValidationException
from baserow.api.user_files.errors import ERROR_USER_FILE_DOES_NOT_EXIST
from baserow.contrib.database.api.fields.errors import (
    ERROR_RICH_TEXT_IMAGE_LIMIT_EXCEEDED,
)
from baserow.contrib.database.fields.exceptions import RichTextImageDoesNotExist


class InvalidJoinParameterException(Exception):
    """
    Raised when an invalid join parameter is provided.
    """


def row_values_validation_error(exc: ValidationError) -> APIException:
    """
    Maps an error raised while preparing row values to the error the client gets.

    :param exc: A single message validation error.
    :return: The rich text image limit or missing image error, or a request body
        validation error.
    """

    if isinstance(exc, RichTextImageDoesNotExist):
        error, status_code, detail = ERROR_USER_FILE_DOES_NOT_EXIST
        detail = detail.format(e=exc)
    elif exc.code == "too_many_images":
        error, status_code, _ = ERROR_RICH_TEXT_IMAGE_LIMIT_EXCEEDED
        detail = exc.message
    else:
        return RequestBodyValidationException(detail=exc.message)

    api_exception = APIException({"error": error, "detail": detail})
    api_exception.status_code = status_code
    return api_exception
