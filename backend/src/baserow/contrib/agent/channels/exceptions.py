class AgentChannelDoesNotExist(Exception):
    """The channel doesn't exist, or can't be used right now."""


class AgentChannelTypeNotAvailable(Exception):
    """The channel type isn't registered, or the workspace can't use it."""
