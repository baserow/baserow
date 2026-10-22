from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_TEMPLATE_DOES_NOT_EXIST = (
    "ERROR_TEMPLATE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested template does not exist.",
)
ERROR_TEMPLATE_FILE_DOES_NOT_EXIST = (
    "ERROR_TEMPLATE_FILE_DOES_NOT_EXIST",
    HTTP_400_BAD_REQUEST,
    "The requested template file does not exist anymore.",
)
ERROR_INVALID_TEMPLATE_ICON = (
    "ERROR_INVALID_TEMPLATE_ICON",
    HTTP_400_BAD_REQUEST,
    "The icon of the template is not allowed.",
)
ERROR_INVALID_TEMPLATE_CATEGORY = (
    "ERROR_INVALID_TEMPLATE_CATEGORY",
    HTTP_400_BAD_REQUEST,
    "The categories of the template are missing or do not exist.",
)
ERROR_TEMPLATE_HAS_NO_CONTENT = (
    "ERROR_TEMPLATE_HAS_NO_CONTENT",
    HTTP_400_BAD_REQUEST,
    "The content of the template was removed.",
)
ERROR_NO_APPLICATIONS_SELECTED = (
    "ERROR_NO_APPLICATIONS_SELECTED",
    HTTP_400_BAD_REQUEST,
    "At least one application must be selected.",
)
ERROR_TEMPLATE_BLOCKED = (
    "ERROR_TEMPLATE_BLOCKED",
    HTTP_400_BAD_REQUEST,
    "The template is blocked and can't be installed.",
)
