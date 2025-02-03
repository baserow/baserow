from rest_framework.status import HTTP_400_BAD_REQUEST

ERROR_INVALID_PROVIDER_URL = (
    "ERROR_INVALID_PROVIDER_URL",
    HTTP_400_BAD_REQUEST,
    "The specified URL doesn't point to a valid provider of the provider type.",
)
