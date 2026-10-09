class AgentDoesNotExist(Exception):
    """The requested agent does not exist or has been trashed."""


class AgentNotInAgentBuilder(Exception):
    def __init__(self, agent_id):
        self.agent_id = agent_id
