from rest_framework import status
from rest_framework.exceptions import APIException


class ApplicationUserLimitReached(APIException):
    """
    Raised when an application user isn't allowed to sign in because the workspace (or
    instance) has reached its application user limit.

    It is a self-describing ``APIException`` so that the plain REST login endpoint
    (``UserSourceObtainJSONWebToken`` in core) renders it directly without needing a
    core-side exception mapping. The enterprise SSO views map it to an
    ``SsoErrorCode`` instead, so the base class is irrelevant there.
    """

    status_code = status.HTTP_402_PAYMENT_REQUIRED

    def __init__(self, detail=None, code=None):
        super().__init__(
            {
                "error": "ERROR_APPLICATION_USER_LIMIT_REACHED",
                "detail": detail
                or (
                    "The application user limit has been reached, please contact the "
                    "application owner."
                ),
            },
            code=code,
        )
