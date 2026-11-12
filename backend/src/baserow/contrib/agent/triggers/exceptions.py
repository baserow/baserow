class AgentTriggerDoesNotExist(Exception):
    """The trigger is missing or trashed."""


class AgentTriggerTypeNotAvailable(Exception):
    """The service type is not a trigger this agent may use."""


class AgentTriggerNoAccess(Exception):
    """The agent's run identity can't read what the trigger watches."""
