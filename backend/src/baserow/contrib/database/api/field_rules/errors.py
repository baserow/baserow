from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

ERROR_RULE_DOES_NOT_EXIST = (
    "ERROR_RULE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested rule does not exist.",
)


ERROR_RULE_TYPE_DOES_NOT_EXIST = (
    "ERROR_RULE_TYPE_DOES_NOT_EXIST",
    HTTP_400_BAD_REQUEST,
    "The requested rule type does not exist.",
)


ERROR_RULE_ALREADY_EXISTS = (
    "ERROR_RULE_ALREADY_EXISTS",
    HTTP_409_CONFLICT,
    "The requested rule already exists.",
)
