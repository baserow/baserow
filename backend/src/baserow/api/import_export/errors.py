from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_RESOURCE_DOES_NOT_EXIST = (
    "ERROR_RESOURCE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested resource does not exist.",
)

ERROR_RESOURCE_IS_INVALID = (
    "ERROR_RESOURCE_IS_INVALID",
    HTTP_400_BAD_REQUEST,
    "The resource is invalid or corrupted.",
)

ERROR_RESOURCE_IS_BEING_IMPORTED = (
    "ERROR_RESOURCE_IS_BEING_IMPORTED",
    HTTP_400_BAD_REQUEST,
    "The resource is currently being imported.",
)

ERROR_UNTRUSTED_PUBLIC_KEY = (
    "ERROR_UNTRUSTED_PUBLIC_KEY",
    HTTP_400_BAD_REQUEST,
    "The public key is not trusted.",
)

ERROR_APPLICATION_IDS_NOT_FOUND = (
    "ERROR_APPLICATION_IDS_NOT_FOUND",
    HTTP_400_BAD_REQUEST,
    "One or more of the specified application IDs were not found in the export file.",
)
