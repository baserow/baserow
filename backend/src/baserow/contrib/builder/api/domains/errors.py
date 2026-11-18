from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_DOMAIN_DOES_NOT_EXIST = (
    "ERROR_DOMAIN_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested domain does not exist.",
)

ERROR_DOMAIN_NOT_IN_BUILDER = (
    "ERROR_DOMAIN_NOT_IN_BUILDER",
    HTTP_400_BAD_REQUEST,
    "The domain id {e.domain_id} does not belong to the builder.",
)

ERROR_DOMAIN_NAME_NOT_UNIQUE = (
    "ERROR_DOMAIN_NAME_NOT_UNIQUE",
    HTTP_400_BAD_REQUEST,
    "The domain name {e.domain_name} already exists.",
)

ERROR_SUB_DOMAIN_HAS_INVALID_DOMAIN_NAME = (
    "ERROR_SUB_DOMAIN_HAS_INVALID_DOMAIN_NAME",
    HTTP_400_BAD_REQUEST,
    "The subdomain {e.domain_name} has an invalid domain name, "
    "you can only use {e.available_domain_names}",
)

ERROR_SUB_DOMAIN_NAME_CONTAINS_DOT = (
    "ERROR_SUB_DOMAIN_NAME_CONTAINS_DOT",
    HTTP_400_BAD_REQUEST,
    "The subdomain {e.domain_name} can't contain a dot in front of the domain name.",
)
