from baserow.contrib.agent.models import AgentApplication
from baserow.core.search.search_types import ApplicationSearchType


class AgentSearchType(ApplicationSearchType):
    type = "agent"
    name = "Agents"
    model_class = AgentApplication
    priority = 5
