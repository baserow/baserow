from baserow.contrib.automation.nodes.models import AIAgentActionNode
from baserow.contrib.automation.nodes.node_types import AutomationNodeActionNodeType
from baserow.contrib.integrations.ai.service_types import AIAgentServiceType


class AIAgentNodeType(AutomationNodeActionNodeType):
    type = "ai_agent"
    model_class = AIAgentActionNode
    service_type = AIAgentServiceType.type
