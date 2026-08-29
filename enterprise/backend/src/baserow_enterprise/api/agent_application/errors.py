from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

ERROR_AGENT_DEFINITION_DOES_NOT_EXIST = (
    "ERROR_AGENT_DEFINITION_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested agent does not exist.",
)

ERROR_AGENT_CHAT_DOES_NOT_EXIST = (
    "ERROR_AGENT_CHAT_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested agent chat does not exist.",
)

ERROR_AGENT_CHAT_ALREADY_RUNNING = (
    "ERROR_AGENT_CHAT_ALREADY_RUNNING",
    HTTP_400_BAD_REQUEST,
    "The chat is still running and cannot accept a new message yet.",
)

ERROR_AGENT_TRIGGER_DOES_NOT_EXIST = (
    "ERROR_AGENT_TRIGGER_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The application has no trigger configured.",
)

ERROR_AGENT_TOOL_DOES_NOT_EXIST = (
    "ERROR_AGENT_TOOL_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested agent tool does not exist.",
)

ERROR_AGENT_MODEL_NOT_CONFIGURED = (
    "ERROR_AGENT_MODEL_NOT_CONFIGURED",
    HTTP_400_BAD_REQUEST,
    "The agent has no usable generative AI model configured.",
)

ERROR_AGENT_CHAT_NOT_RETRYABLE = (
    "ERROR_AGENT_CHAT_NOT_RETRYABLE",
    HTTP_400_BAD_REQUEST,
    "The chat did not fail, so there is nothing to retry.",
)

ERROR_AGENT_CHAT_AWAITING_APPROVAL = (
    "ERROR_AGENT_CHAT_AWAITING_APPROVAL",
    HTTP_400_BAD_REQUEST,
    "The chat has pending tool approvals that must be decided first.",
)

ERROR_AGENT_TOOL_APPROVAL_DOES_NOT_EXIST = (
    "ERROR_AGENT_TOOL_APPROVAL_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested tool approval does not exist or has already been decided.",
)

ERROR_AGENT_CHAT_CHANNEL_DOES_NOT_EXIST = (
    "ERROR_AGENT_CHAT_CHANNEL_DOES_NOT_EXIST",
    HTTP_404_NOT_FOUND,
    "The requested chat channel does not exist.",
)
