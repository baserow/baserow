from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_ELEMENT_DOES_NOT_EXIST = (
    "ERROR_ELEMENT_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested element does not exist.",
)

ERROR_ELEMENT_TYPE_DEACTIVATED = (
    "ERROR_ELEMENT_TYPE_DEACTIVATED",
    HTTP_400_BAD_REQUEST,
    "The element type is deactivated.",
)

ERROR_ELEMENT_NOT_IN_SAME_PAGE = (
    "ERROR_ELEMENT_NOT_IN_SAME_PAGE",
    HTTP_400_BAD_REQUEST,
    "The given elements do not belong to the same page.",
)

ERROR_ELEMENT_PROPERTY_OPTIONS_NOT_UNIQUE = (
    "ERROR_ELEMENT_PROPERTY_OPTIONS_NOT_UNIQUE",
    HTTP_400_BAD_REQUEST,
    "The provided schema_property are not unique.",
)
