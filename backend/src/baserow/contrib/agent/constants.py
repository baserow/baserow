from enum import StrEnum

from baserow.core.agents.subjects import AgentSubjectType


class AgentReadinessState(StrEnum):
    """Whether an Agent's required configuration allows it to reply."""

    READY = "ready"
    INCOMPLETE = "incomplete"
    UNAVAILABLE = "unavailable"


class AgentConfigurationErrorCode(StrEnum):
    """Why a configuration field prevents an Agent from being ready."""

    REQUIRED = "required"
    UNAVAILABLE = "unavailable"


class AgentRunAsState(StrEnum):
    """Availability of an Agent's configured workspace identity."""

    UNSET = "unset"
    ACTIVE = "active"
    TRASHED = "trashed"
    MISSING = "missing"


AGENT_RUN_TYPE = "agent"
RUN_AS_SUBJECT_TYPES = [AgentSubjectType.type]
HISTORY_MESSAGE_LIMIT = 20
REPLY_REQUEST_LIMIT = 20
AGENT_NOT_READY = "not_ready"
AGENT_NOT_ALLOWED = "not_allowed"
INTERRUPTED_REPLY_NOTE = "[This reply was interrupted and may be incomplete.]"
INTERRUPTED_CHANGES_NOTE = (
    "[Changes started before the interruption: {changes}. A stopped change may "
    "have completed; check before repeating it.]"
)
UNAVAILABLE_WORKSPACE_ACCESS_INSTRUCTIONS = (
    "The identity configured for your workspace access is no longer available. "
    "You cannot read or change workspace data. When a request needs workspace "
    "access, explain that the configured identity is unavailable and ask the user "
    "to have someone with the right permissions restore the identity or select an "
    "active Run as identity in Workspace access. Continue helping with requests "
    "that do not need workspace access."
)
TOOL_RETRIES = 3
STEP_RESOURCE_LIMIT = 500
STEP_RESOURCE_NAME_MAX_LENGTH = 255
STEP_TARGET_MAX_LENGTH = 512
