from baserow.contrib.automation.nodes.node_types import AutomationNodeActionNodeType
from baserow_enterprise.automation.nodes.models import CoreCodeActionNode
from baserow_enterprise.integrations.core.service_types import CoreCodeServiceType


class CoreCodeNodeType(AutomationNodeActionNodeType):
    type = "code"
    model_class = CoreCodeActionNode
    service_type = CoreCodeServiceType.type
