from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

ERROR_TWO_FACTOR_AUTH_TYPE_DOES_NOT_EXIST = (
    "ERROR_TWO_FACTOR_AUTH_TYPE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested auth provider does not exist.",
)

ERROR_TWO_FACTOR_AUTH_VERIFICATION_FAILED = (
    "ERROR_TWO_FACTOR_AUTH_VERIFICATION_FAILED",
    HTTP_401_UNAUTHORIZED,
    "Two-factor authentication verification failed.",
)

ERROR_WRONG_PASSWORD = (
    "ERROR_WRONG_PASSWORD",
    HTTP_403_FORBIDDEN,
    "The provided password is incorrect.",
)

ERROR_TWO_FACTOR_AUTH_ALREADY_CONFIGURED = (
    "ERROR_TWO_FACTOR_AUTH_ALREADY_CONFIGURED",
    HTTP_400_BAD_REQUEST,
    "Two-factor authentication already configured",
)

ERROR_TWO_FACTOR_AUTH_NOT_CONFIGURED = (
    "ERROR_TWO_FACTOR_AUTH_NOT_CONFIGURED",
    HTTP_400_BAD_REQUEST,
    "Two-factor authentication not configured",
)

ERROR_TWO_FACTOR_AUTH_CANNOT_BE_CONFIGURED = (
    "ERROR_TWO_FACTOR_AUTH_CANNOT_BE_CONFIGURED",
    HTTP_400_BAD_REQUEST,
    "Two-factor authentication cannot be configured",
)
