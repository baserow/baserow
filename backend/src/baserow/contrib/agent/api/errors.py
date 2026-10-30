ERROR_AGENT_CONVERSATION_DOES_NOT_EXIST = (
    "ERROR_AGENT_CONVERSATION_DOES_NOT_EXIST",
    404,
    "The requested agent conversation does not exist.",
)
ERROR_AGENT_MESSAGE_CONFLICT = (
    "ERROR_AGENT_MESSAGE_CONFLICT",
    409,
    "This message identifier has already been used for a different message.",
)
ERROR_AGENT_NOT_READY = (
    "ERROR_AGENT_NOT_READY",
    400,
    "The agent must have an available saved configuration before accepting messages.",
)
ERROR_AGENT_BUSY = (
    "ERROR_AGENT_BUSY",
    429,
    "Agents in this workspace are busy. Try again shortly.",
)
