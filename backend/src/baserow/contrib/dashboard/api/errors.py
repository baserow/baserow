from rest_framework.status import HTTP_401_UNAUTHORIZED, HTTP_404_NOT_FOUND

ERROR_DASHBOARD_DOES_NOT_EXIST = (
    "ERROR_DASHBOARD_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested dashboard does not exist.",
)
ERROR_NO_AUTHORIZATION_TO_PUBLIC_DASHBOARD = (
    "ERROR_NO_AUTHORIZATION_TO_PUBLIC_DASHBOARD",
    HTTP_401_UNAUTHORIZED,
    "A valid password is required to access this password protected dashboard.",
)
