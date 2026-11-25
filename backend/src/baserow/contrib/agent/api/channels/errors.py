from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_AGENT_CHANNEL_DOES_NOT_EXIST = (
    "ERROR_AGENT_CHANNEL_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested agent channel does not exist.",
)
ERROR_AGENT_CHANNEL_TYPE_NOT_AVAILABLE = (
    "ERROR_AGENT_CHANNEL_TYPE_NOT_AVAILABLE",
    HTTP_400_BAD_REQUEST,
    "This channel type isn't offered on this instance or the workspace's license "
    "doesn't cover it.",
)
