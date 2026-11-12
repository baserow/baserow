class AgentActionDoesNotExist(Exception):
    """The requested action is absent, trashed or belongs to another agent."""


class AgentActionTypeNotAvailable(Exception):
    """This service type is not offered as an action for the agent."""
