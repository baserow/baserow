from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_DATA_SOURCE_DOES_NOT_EXIST = (
    "ERROR_DATA_SOURCE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested data_source does not exist.",
)


ERROR_DATA_SOURCE_NOT_IN_SAME_PAGE = (
    "ERROR_DATA_SOURCE_NOT_IN_SAME_PAGE",
    HTTP_400_BAD_REQUEST,
    "The given data_sources do not belong to the same page.",
)

ERROR_DATA_DOES_NOT_EXIST = (
    "ERROR_DATA_SOURCE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested data does not exist.",
)

ERROR_DATA_SOURCE_CANNOT_USE_SERVICE_TYPE = (
    "ERROR_DATA_SOURCE_CANNOT_USE_SERVICE_TYPE",
    HTTP_400_BAD_REQUEST,
    "A data_source cannot be created or updated with this service_type.",
)

ERROR_DATA_SOURCE_REFINEMENT_FORBIDDEN = (
    "ERROR_DATA_SOURCE_REFINEMENT_FORBIDDEN",
    HTTP_400_BAD_REQUEST,
    "Data source filter, search and/or sort fields error: {e}",
)

ERROR_DATA_SOURCE_NAME_NOT_UNIQUE = (
    "ERROR_DATA_SOURCE_NAME_NOT_UNIQUE",
    HTTP_400_BAD_REQUEST,
    "The data source name '{e}' already exists.",
)
