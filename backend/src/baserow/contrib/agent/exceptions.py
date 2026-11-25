class AgentConversationDoesNotExist(Exception):
    """The conversation is missing or belongs to another owner or agent."""


class AgentMessageConflict(Exception):
    """A client identifier has already been accepted with different content."""


class AgentNotReady(Exception):
    """The agent's saved configuration isn't ready to accept new messages."""


class AgentRunAsSubjectDoesNotExist(Exception):
    """The subject to run as is missing, trashed or in another workspace."""


class AgentConversationWaitingForApproval(Exception):
    """The conversation's latest reply waits for decisions on its held calls."""


class AgentToolRequirementsMissing(Exception):
    """Allowed tools leave out tools they require."""

    def __init__(self, missing: dict[str, list[str]]):
        """
        :param missing: The required tools left out, by the tool requiring them.
        """

        self.missing = missing
        super().__init__(
            "; ".join(
                f"{name} requires {', '.join(required)}"
                for name, required in missing.items()
            )
        )


class AgentToolApprovalNotPending(Exception):
    """The approval is decided or isn't held by the conversation's waiting reply."""


class AgentTriggerOff(Exception):
    """The trigger of a shared conversation is off or gone, so its reply stops."""
