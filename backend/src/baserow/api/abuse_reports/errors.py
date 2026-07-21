from rest_framework.status import HTTP_400_BAD_REQUEST

ERROR_ABUSE_REPORTING_DISABLED = (
    "ERROR_ABUSE_REPORTING_DISABLED",
    HTTP_400_BAD_REQUEST,
    "Reporting abuse has been disabled by the instance administrator.",
)
ERROR_ABUSE_REPORT_RESOURCE_TYPE_DOES_NOT_EXIST = (
    "ERROR_ABUSE_REPORT_RESOURCE_TYPE_DOES_NOT_EXIST",
    HTTP_400_BAD_REQUEST,
    "The provided abuse report resource type does not exist.",
)
