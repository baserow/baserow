class AgentDefinitionDoesNotExist(Exception):
    """Raised when the requested agent definition doesn't exist."""


class AgentChatDoesNotExist(Exception):
    """Raised when the requested agent chat doesn't exist."""


class AgentChatAlreadyRunning(Exception):
    """Raised when a message is sent to a chat that is still running."""


class AgentTriggerDoesNotExist(Exception):
    """Raised when the application has no trigger configured."""


class AgentToolDoesNotExist(Exception):
    """Raised when the requested agent tool doesn't exist."""


class AgentModelNotConfigured(Exception):
    """Raised when the agent has no usable generative AI model configured."""


class AgentChatRunCancelled(Exception):
    """Raised when a running agent chat turn was cancelled."""


class AgentChatAwaitingApproval(Exception):
    """
    Raised when a message is sent to a chat that is paused on tool calls
    awaiting approval; the approvals must be decided first.
    """


class AgentToolApprovalDoesNotExist(Exception):
    """Raised when a requested tool approval doesn't exist or isn't pending."""


class AgentChatNotRetryable(Exception):
    """
    Raised when a chat run retry is requested but the chat is not in an
    error state or has nothing to retry.
    """


class AgentChatChannelDoesNotExist(Exception):
    """Raised when the requested chat channel doesn't exist."""
