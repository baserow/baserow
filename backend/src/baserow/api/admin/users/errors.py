from rest_framework.status import HTTP_400_BAD_REQUEST

USER_ADMIN_CANNOT_DEACTIVATE_SELF = (
    "USER_ADMIN_CANNOT_DEACTIVATE_SELF",
    HTTP_400_BAD_REQUEST,
    "You cannot de-activate or un-staff yourself.",
)

USER_ADMIN_CANNOT_DELETE_SELF = (
    "USER_ADMIN_CANNOT_DELETE_SELF",
    HTTP_400_BAD_REQUEST,
    "You cannot delete yourself.",
)

USER_ADMIN_UNKNOWN_USER = (
    "USER_ADMIN_UNKNOWN_USER",
    HTTP_400_BAD_REQUEST,
    "Unknown user supplied.",
)

USER_ADMIN_ALREADY_EXISTS = (
    "USER_ADMIN_ALREADY_EXISTS",
    HTTP_400_BAD_REQUEST,
    "A user with that username/email already exists.",
)
