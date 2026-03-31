from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

ERROR_FORM_DOES_NOT_EXIST = (
    "ERROR_FORM_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested form does not exist.",
)
ERROR_FORM_VIEW_FIELD_TYPE_IS_NOT_SUPPORTED = (
    "ERROR_FORM_VIEW_FIELD_TYPE_IS_NOT_SUPPORTED",
    HTTP_400_BAD_REQUEST,
    "The {e.field_type} field type is not compatible with the form view.",
)
ERROR_FORM_VIEW_READ_ONLY_FIELD_IS_NOT_SUPPORTED = (
    "ERROR_FORM_VIEW_READ_ONLY_FIELD_IS_NOT_SUPPORTED",
    HTTP_400_BAD_REQUEST,
    "The {e.field_name} field is read only and not compatible with the form view.",
)
ERROR_NO_PERMISSION_TO_PUBLICLY_SHARED_FORM = (
    "ERROR_NO_PERMISSION_TO_PUBLICLY_SHARED_FORM",
    HTTP_401_UNAUTHORIZED,
    "The user does not have the permissions to see this password protected shared form.",
)

ERROR_VIEW_HAS_NO_PUBLIC_FILE_FIELD = (
    "ERROR_VIEW_HAS_NO_PUBLIC_FILE_FIELD",
    HTTP_400_BAD_REQUEST,
    "The view has no public file field.",
)
ERROR_FORM_VIEW_FIELD_OPTIONS_CONDITION_GROUP_DOES_NOT_EXIST = (
    "ERROR_FORM_VIEW_FIELD_OPTIONS_CONDITION_GROUP_DOES_NOT_EXIST",
    HTTP_400_BAD_REQUEST,
    "The provided form view field options condition group does not exists.",
)
ERROR_INVALID_EDIT_ROW_TOKEN = (
    "ERROR_INVALID_EDIT_ROW_TOKEN",
    HTTP_404_NOT_FOUND,
    "The provided edit token is invalid or does not match the requested row.",
)
