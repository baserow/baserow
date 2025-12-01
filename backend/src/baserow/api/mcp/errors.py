from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_MCP_ENDPOINT_DOES_NOT_EXIST = (
    "ERROR_MCP_ENDPOINT_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested MCP endpoint does not exist.",
)

ERROR_MCP_ENDPOINT_DOES_NOT_BELONG_TO_USER = (
    "ERROR_MCP_ENDPOINT_DOES_NOT_BELONG_TO_USER",
    HTTP_400_BAD_REQUEST,
    "The requested MCP endpoint does not belong to this user.",
)

ERROR_MAXIMUM_UNIQUE_ENDPOINT_TRIES = (
    "ERROR_MAXIMUM_UNIQUE_ENDPOINT_TRIES",
    HTTP_400_BAD_REQUEST,
    "The maximum amount of tries has been exceeded when generating a unique MCP endpoint key.",
)
