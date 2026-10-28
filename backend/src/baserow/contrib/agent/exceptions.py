class AgentConversationDoesNotExist(Exception):
    """The conversation is missing or belongs to another owner or agent."""


class AgentMessageConflict(Exception):
    """A client identifier has already been accepted with different content."""


class AgentNotReady(Exception):
    """The agent's saved configuration isn't ready to accept new messages."""


class AgentRunAsSubjectDoesNotExist(Exception):
    """The subject to run as is missing, trashed or in another workspace."""
