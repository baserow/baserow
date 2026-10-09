from baserow.core.search.search_types import ApplicationSearchType
from baserow_enterprise.agent_builder.models import AgentBuilder


class AgentBuilderSearchType(ApplicationSearchType):
    type = "agent_builder"
    name = "Agent builders"
    model_class = AgentBuilder
    priority = 5
