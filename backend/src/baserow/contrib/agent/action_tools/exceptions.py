class AgentActionDoesNotExist(Exception):
    """The requested action is absent, trashed or belongs to another agent."""


class AgentActionTypeNotAvailable(Exception):
    """This service type is not offered as an action for the agent."""


class AgentActionLimitReached(Exception):
    """The agent already has as many actions as this instance allows."""

    def __init__(self, limit: int) -> None:
        """
        :param limit: The most actions one agent can have.
        """

        self.limit = limit
        super().__init__(f"The agent has reached its action limit ({limit}).")


class AgentActionCallNotPrepared(Exception):
    """An approved call came back without the values its approver read."""
