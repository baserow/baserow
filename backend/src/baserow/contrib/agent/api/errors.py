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
ERROR_AGENT_RUN_AS_SUBJECT_DOES_NOT_EXIST = (
    "ERROR_AGENT_RUN_AS_SUBJECT_DOES_NOT_EXIST",
    400,
    "The identity to run as does not exist in this workspace or is trashed.",
)
ERROR_AGENT_BUSY = (
    "ERROR_AGENT_BUSY",
    429,
    "Agents in this workspace are busy. Try again shortly.",
)
ERROR_AGENT_CONVERSATION_WAITING_FOR_APPROVAL = (
    "ERROR_AGENT_CONVERSATION_WAITING_FOR_APPROVAL",
    409,
    "Approve or reject the agent's held steps before sending a new message.",
)
ERROR_AGENT_TOOL_APPROVAL_NOT_PENDING = (
    "ERROR_AGENT_TOOL_APPROVAL_NOT_PENDING",
    409,
    "These steps are not waiting for a decision any more.",
)
ERROR_AGENT_CONVERSATION_READ_ONLY = (
    "ERROR_AGENT_CONVERSATION_READ_ONLY",
    409,
    "This conversation was started by a trigger and is read-only.",
)
