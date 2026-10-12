from baserow.core.search.search_types import ApplicationSearchType
from baserow_enterprise.agent.models import AgentApplication


class AgentSearchType(ApplicationSearchType):
    type = "agent"
    name = "Agents"
    model_class = AgentApplication
    priority = 5
