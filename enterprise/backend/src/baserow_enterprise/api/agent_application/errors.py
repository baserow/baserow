from rest_framework.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
    HTTP_429_TOO_MANY_REQUESTS,
)

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
ERROR_PUBLIC_CHAT_AUTHORIZATION_REQUIRED = (
    "ERROR_PUBLIC_CHAT_AUTHORIZATION_REQUIRED",
    HTTP_401_UNAUTHORIZED,
    "This chat is password protected; authorize first.",
)
ERROR_PUBLIC_CHAT_MESSAGE_LIMIT_REACHED = (
    "ERROR_PUBLIC_CHAT_MESSAGE_LIMIT_REACHED",
    HTTP_400_BAD_REQUEST,
    "This conversation has reached its message limit. Start a new one.",
)
ERROR_PUBLIC_CHAT_RATE_LIMIT_EXCEEDED = (
    "ERROR_PUBLIC_CHAT_RATE_LIMIT_EXCEEDED",
    HTTP_429_TOO_MANY_REQUESTS,
    "Too many messages, please wait a moment.",
)
ERROR_AGENT_CHAT_NOT_OWNED = (
    "ERROR_AGENT_CHAT_NOT_OWNED",
    403,
    "Only the user who started this conversation can continue it.",
)
