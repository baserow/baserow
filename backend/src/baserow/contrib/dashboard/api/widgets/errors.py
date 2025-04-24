from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_WIDGET_DOES_NOT_EXIST = (
    "ERROR_WIDGET_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested widget does not exist.",
)

ERROR_WIDGET_TYPE_DOES_NOT_EXIST = (
    "ERROR_WIDGET_TYPE_DOES_NOT_EXIST",
    HTTP_400_BAD_REQUEST,
    "The requested widget type does not exist.",
)

ERROR_WIDGET_IMPROPERLY_CONFIGURED = (
    "ERROR_WIDGET_IMPROPERLY_CONFIGURED",
    HTTP_400_BAD_REQUEST,
    "The requested configuration is not allowed.",
)
