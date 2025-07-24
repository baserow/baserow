from rest_framework.status import HTTP_404_NOT_FOUND

ERROR_RULE_DOES_NOT_EXIST = (
    "ERROR_RULE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested rule does not exist.",
)


ERROR_RULE_TYPE_DOES_NOT_EXIST = (
    "ERROR_RULE_TYPE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested rule type does not exist.",
)
