from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_GROUP_USER_DOES_NOT_EXIST = (
    "ERROR_GROUP_USER_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested group user does not exist.",
)
ERROR_GROUP_USER_ALREADY_EXISTS = (
    "ERROR_GROUP_USER_ALREADY_EXISTS",
    HTTP_400_BAD_REQUEST,
    "The user is already a member of the group.",
)
ERROR_CANNOT_DELETE_YOURSELF_FROM_GROUP = (
    "ERROR_CANNOT_DELETE_YOURSELF_FROM_GROUP",
    HTTP_400_BAD_REQUEST,
    "You cannot delete yourself from the group. Use the leave group endpoint for that.",
)
