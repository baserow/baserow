class AgentConversationDoesNotExist(Exception):
    """The conversation is missing or belongs to another owner or agent."""


class AgentMessageConflict(Exception):
    """A client identifier has already been accepted with different content."""


class AgentNotReady(Exception):
    """The agent's saved configuration isn't ready to accept new messages."""


class AgentRunAsSubjectDoesNotExist(Exception):
    """The subject to run as is missing, trashed or in another workspace."""


class AgentConversationWaitingForApproval(Exception):
    """The conversation's latest reply waits for a participant to decide its held calls."""


class AgentToolApprovalNotPending(Exception):
    """The approval is decided or isn't held by the conversation's waiting reply."""


class AgentToolDecisionInvalid(Exception):
    """A decision's answer doesn't fit the held call it decides."""


class AgentTriggerOff(Exception):
    """The trigger of a shared conversation is off or gone, so its reply stops."""
