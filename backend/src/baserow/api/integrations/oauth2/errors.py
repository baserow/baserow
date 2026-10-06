from rest_framework.status import HTTP_400_BAD_REQUEST

ERROR_OAUTH2_INTEGRATION_NOT_CONFIGURED = (
    "ERROR_OAUTH2_INTEGRATION_NOT_CONFIGURED",
    HTTP_400_BAD_REQUEST,
    "Save the client id and client secret of the integration before connecting it.",
)
ERROR_OAUTH2_INVALID_RETURN_URL = (
    "ERROR_OAUTH2_INVALID_RETURN_URL",
    HTTP_400_BAD_REQUEST,
    "The page to return to must belong to this Baserow installation.",
)
ERROR_OAUTH2_NOT_SUPPORTED = (
    "ERROR_OAUTH2_NOT_SUPPORTED",
    HTTP_400_BAD_REQUEST,
    "This integration type cannot be connected to an account.",
)
