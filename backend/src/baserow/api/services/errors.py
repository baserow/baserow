from rest_framework.status import HTTP_400_BAD_REQUEST

ERROR_SERVICE_INVALID_TYPE = (
    "ERROR_SERVICE_INVALID_TYPE",
    HTTP_400_BAD_REQUEST,
    "The service type does not exist.",
)

ERROR_SERVICE_FILTER_PROPERTY_DOES_NOT_EXIST = (
    "ERROR_SERVICE_FILTER_PROPERTY_DOES_NOT_EXIST",
    HTTP_400_BAD_REQUEST,
    "A data source filter is misconfigured: {e}",
)

ERROR_SERVICE_SORT_PROPERTY_DOES_NOT_EXIST = (
    "ERROR_SERVICE_SORT_PROPERTY_DOES_NOT_EXIST",
    HTTP_400_BAD_REQUEST,
    "A data source sort is misconfigured: {e}",
)
