from rest_framework.status import HTTP_400_BAD_REQUEST

ERROR_CANNOT_DELETE_A_TEMPLATE_GROUP = (
    "ERROR_CANNOT_DELETE_A_TEMPLATE_GROUP",
    HTTP_400_BAD_REQUEST,
    "You cannot delete a template group as it is used by the template system.",
)
