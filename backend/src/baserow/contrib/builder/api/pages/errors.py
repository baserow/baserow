from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_PAGE_DOES_NOT_EXIST = (
    "ERROR_PAGE_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested page does not exist.",
)


ERROR_SHARED_PAGE_READ_ONLY = (
    "ERROR_SHARED_PAGE_READ_ONLY",
    HTTP_400_BAD_REQUEST,
    "The shared page is read-only and cannot be affected.",
)

ERROR_PAGE_NOT_IN_BUILDER = (
    "ERROR_PAGE_NOT_IN_BUILDER",
    HTTP_400_BAD_REQUEST,
    "The page id {e.page_id} does not belong to the builder.",
)

ERROR_PAGE_NAME_NOT_UNIQUE = (
    "ERROR_PAGE_NAME_NOT_UNIQUE",
    HTTP_400_BAD_REQUEST,
    "The page name {e.name} already exists for your builder instance.",
)

ERROR_PAGE_PATH_NOT_UNIQUE = (
    "ERROR_PAGE_PATH_NOT_UNIQUE",
    HTTP_400_BAD_REQUEST,
    "The page path {e.path} already exists for your builder instance.",
)

ERROR_PATH_PARAM_NOT_IN_PATH = (
    "ERROR_PATH_PARAM_NOT_IN_PATH",
    HTTP_400_BAD_REQUEST,
    "The path param {e.path_param_name} doesn't exist in path {e.path}",
)

ERROR_PATH_PARAM_NOT_DEFINED = (
    "ERROR_PATH_PARAM_NOT_DEFINED",
    HTTP_400_BAD_REQUEST,
    "The path param {e.path_param_name} in path {e.path} has not been defined in the "
    "given path params of {e.path_param_names}",
)

ERROR_DUPLICATE_PATH_PARAMS_IN_PATH = (
    "ERROR_DUPLICATE_PATH_PARAMS_IN_PATH",
    HTTP_400_BAD_REQUEST,
    "The path params {e.path_param_names} are defined multiple times in path {e.path}",
)

ERROR_INVALID_QUERY_PARAM_NAME = (
    "ERROR_INVALID_QUERY_PARAM_NAME",
    HTTP_400_BAD_REQUEST,
    "The provided query parameter name {e.query_param_name} is invalid. Query parameter "
    "names must contain only letters, numbers and underscores.",
)

ERROR_DUPLICATE_QUERY_PARAMS = (
    "ERROR_DUPLICATE_QUERY_PARAMS",
    HTTP_400_BAD_REQUEST,
    "The query parameter {e.param} is either defined multiple times in {e.query_param_names} "
    "or conflicts with path parameters {e.path_param_names}.",
)
