from baserow.contrib.automation.nodes.node_types import AutomationNodeActionNodeType
from baserow_enterprise.automation.nodes.models import CoreCodeActionNode
from baserow_enterprise.features import CODE_RUNNER
from baserow_enterprise.integrations.core.service_types import CoreCodeServiceType
from baserow_premium.license.handler import LicenseHandler


class CoreCodeNodeType(AutomationNodeActionNodeType):
    type = "code"
    model_class = CoreCodeActionNode
    service_type = CoreCodeServiceType.type

    def is_deactivated(self, workspace) -> bool:
        return not LicenseHandler.workspace_has_feature(CODE_RUNNER, workspace)

    def raise_if_deactivated(self, workspace) -> None:
        LicenseHandler.raise_if_workspace_doesnt_have_feature(CODE_RUNNER, workspace)
