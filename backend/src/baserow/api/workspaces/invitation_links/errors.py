from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

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
