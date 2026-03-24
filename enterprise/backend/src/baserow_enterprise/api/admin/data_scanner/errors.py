from rest_framework.status import HTTP_404_NOT_FOUND, HTTP_409_CONFLICT

ERROR_DATA_SCAN_DOES_NOT_EXIST = (
    "ERROR_DATA_SCAN_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested data scan does not exist.",
)

ERROR_DATA_SCAN_ALREADY_RUNNING = (
    "ERROR_DATA_SCAN_ALREADY_RUNNING",
    HTTP_409_CONFLICT,
    "The data scan is already running.",
)

ERROR_DATA_SCAN_RESULT_DOES_NOT_EXIST = (
    "ERROR_DATA_SCAN_RESULT_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested data scan result does not exist.",
)
