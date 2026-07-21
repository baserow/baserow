from rest_framework.status import HTTP_401_UNAUTHORIZED

ERROR_BUILDER_PREVIEW_SESSION_INVALID = (
    "ERROR_BUILDER_PREVIEW_SESSION_INVALID",
    HTTP_401_UNAUTHORIZED,
    "The builder preview session is missing, invalid, or expired.",
)
