from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_GROUP_INVITATION_DOES_NOT_EXIST = (
    "ERROR_GROUP_INVITATION_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested group invitation does not exist.",
)
ERROR_GROUP_INVITATION_EMAIL_MISMATCH = (
    "ERROR_GROUP_INVITATION_EMAIL_MISMATCH",
    HTTP_400_BAD_REQUEST,
    "Your email address does not match with the invitation.",
)
