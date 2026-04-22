from django.conf import settings
from django.http import JsonResponse

from rest_framework import status
from rest_framework.exceptions import APIException, Throttled, ValidationError


def api_exception_to_json_response(exc: APIException) -> JsonResponse:
    """
    Serialize a DRF ``APIException`` the same way DRF's default
    ``exception_handler`` does, for use in Django middleware that runs before
    the DRF view and therefore outside the handler's reach.
    """

    detail = exc.detail
    data = detail if isinstance(detail, (list, dict)) else {"detail": str(detail)}
    response = JsonResponse(data, status=exc.status_code, safe=False)
    if getattr(exc, "auth_header", None):
        response["WWW-Authenticate"] = exc.auth_header
    if getattr(exc, "wait", None):
        response["Retry-After"] = "%d" % exc.wait
    return response


class RequestBodyValidationException(APIException):
    def __init__(self, detail=None, code=None):
        super().__init__(
            {"error": "ERROR_REQUEST_BODY_VALIDATION", "detail": detail}, code=code
        )
        self.status_code = 400


class UnknownFieldProvided(ValidationError):
    """
    Raised when an unknown field is provided to an API endpoint.
    """


class QueryParameterValidationException(APIException):
    def __init__(self, detail=None, code=None):
        super().__init__(
            {"error": "ERROR_QUERY_PARAMETER_VALIDATION", "detail": detail}, code=code
        )
        self.status_code = 400


class ThrottledAPIException(Throttled):
    pass


class InvalidClientSessionIdAPIException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "ERROR_INVALID_CLIENT_SESSION_ID"
    default_detail = (
        f"An invalid {settings.CLIENT_SESSION_ID_HEADER} header was provided. It must "
        f"be between 1 and {settings.MAX_CLIENT_SESSION_ID_LENGTH} characters long and "
        f"must only contain alphanumeric or the - characters.",
    )


class InvalidUndoRedoActionGroupIdAPIException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "ERROR_INVALID_CLIENT_ACTION_GROUP"
    default_detail = (
        f"An invalid {settings.CLIENT_UNDO_REDO_ACTION_GROUP_ID_HEADER} header was provided. "
        f"It must be a valid Version 4 UUID.",
    )


class InvalidSortDirectionException(Exception):
    """
    Raised when an invalid sort direction is provided.
    """


class InvalidSortAttributeException(Exception):
    """
    Raised when a sort is requested for an invalid or non-existent field.
    """
