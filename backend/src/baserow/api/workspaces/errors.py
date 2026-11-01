from rest_framework.status import HTTP_400_BAD_REQUEST

ERROR_GROUP_USER_IS_LAST_ADMIN = (
    "ERROR_GROUP_USER_IS_LAST_ADMIN",
    HTTP_400_BAD_REQUEST,
    "The related user is the last admin in the group. They must delete the group or "
    "give someone else admin permissions.",
)

ERROR_INVALID_WORKSPACE_ROLE = (
    "ERROR_INVALID_WORKSPACE_ROLE",
    HTTP_400_BAD_REQUEST,
    "The provided role is not available in the workspace.",
)
