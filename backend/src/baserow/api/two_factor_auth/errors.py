from rest_framework.status import HTTP_404_NOT_FOUND, HTTP_401_UNAUTHORIZED


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
