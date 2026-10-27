from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_DASHBOARD_FILTER_DOES_NOT_EXIST = (
    "ERROR_DASHBOARD_FILTER_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested dashboard filter does not exist.",
)

ERROR_DASHBOARD_FILTER_ORDER_INVALID = (
    "ERROR_DASHBOARD_FILTER_ORDER_INVALID",
    HTTP_400_BAD_REQUEST,
    "The order must contain distinct IDs of existing filters in this dashboard.",
)

ERROR_DASHBOARD_FILTER_INVALID_CONFIGURATION = (
    "ERROR_DASHBOARD_FILTER_INVALID_CONFIGURATION",
    HTTP_400_BAD_REQUEST,
    "The operator is not compatible with this dashboard filter type.",
)


ERROR_DASHBOARD_FILTER_OPTIONS_EXPIRED = (
    "ERROR_DASHBOARD_FILTER_OPTIONS_EXPIRED",
    HTTP_400_BAD_REQUEST,
    "These filter options have expired or changed. Refresh the options to continue.",
)
ERROR_DASHBOARD_FILTER_OPTIONS_TOO_LARGE = (
    "ERROR_DASHBOARD_FILTER_OPTIONS_TOO_LARGE",
    HTTP_400_BAD_REQUEST,
    "These choices exceed the data limit. Use a smaller source or a simpler formula.",
)


ERROR_DASHBOARD_FILTER_INVALID_VALUES = (
    "ERROR_DASHBOARD_FILTER_INVALID_VALUES",
    HTTP_400_BAD_REQUEST,
    "Selected values must be text, with at most 1,000 values and 64 KiB "
    "in total across this dashboard's filters.",
)
