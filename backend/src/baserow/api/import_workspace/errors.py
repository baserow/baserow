from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_RESOURCE_DOES_NOT_EXIST = (
    "ERROR_RESOURCE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested resource does not exist.",
)

ERROR_RESOURCE_IS_CORRUPTED = (
    "ERROR_RESOURCE_IS_CORRUPTED",
    HTTP_400_BAD_REQUEST,
    "The resource is corrupted.",
)
