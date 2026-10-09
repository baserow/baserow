from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_AGENT_DOES_NOT_EXIST = (
    "ERROR_AGENT_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested agent does not exist.",
)

ERROR_AGENT_NOT_IN_AGENT_BUILDER = (
    "ERROR_AGENT_NOT_IN_AGENT_BUILDER",
    HTTP_400_BAD_REQUEST,
    "The agent ID {e.agent_id} does not belong to the agent builder.",
)
