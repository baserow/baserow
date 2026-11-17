from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST = (
    "ERROR_WORKSPACE_INVITATION_LINK_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested workspace invitation link does not exist.",
)
ERROR_WORKSPACE_INVITATION_LINK_SIGNUPS_DISABLED = (
    "ERROR_WORKSPACE_INVITATION_LINK_SIGNUPS_DISABLED",
    HTTP_400_BAD_REQUEST,
    "Invitation links can't be created while both new signups and signups via "
    "workspace invitations are disabled.",
)
ERROR_WORKSPACE_INVITATION_LINK_PASSWORD_REQUIRED = (
    "ERROR_WORKSPACE_INVITATION_LINK_PASSWORD_REQUIRED",
    HTTP_401_UNAUTHORIZED,
    "A valid password is required to use this password protected invitation link.",
)
