AGENT_RUN_TYPE = "agent"
RUN_AS_SUBJECT_TYPES = ["core.Agent"]
HISTORY_MESSAGE_LIMIT = 20
REPLY_REQUEST_LIMIT = 3
AGENT_NOT_READY = "not_ready"
AGENT_NOT_ALLOWED = "not_allowed"
INTERRUPTED_REPLY_NOTE = "[This reply was interrupted and may be incomplete.]"
UNAVAILABLE_WORKSPACE_ACCESS_INSTRUCTIONS = (
    "The identity configured for your workspace access is no longer available. "
    "You cannot read or change workspace data. When a request needs workspace "
    "access, explain that the configured identity is unavailable and ask the user "
    "to have someone with the right permissions restore the identity or select an "
    "active Run as identity in Workspace access. Continue helping with requests "
    "that do not need workspace access."
)
