from baserow.contrib.automation.nodes.node_types import AutomationNodeActionNodeType
from baserow_enterprise.automation.nodes.models import (
    CoreCodeActionNode,
    CoreXLSFileReaderActionNode,
)
from baserow_enterprise.features import CODE_RUNNER, XLS_FILE_READER
from baserow_enterprise.integrations.core.service_types import (
    CoreCodeServiceType,
    CoreXLSFileReaderServiceType,
)
from baserow_premium.license.handler import LicenseHandler


class CoreCodeNodeType(AutomationNodeActionNodeType):
    type = "code"
    model_class = CoreCodeActionNode
    service_type = CoreCodeServiceType.type

    def is_deactivated(self, workspace) -> bool:
        return not LicenseHandler.workspace_has_feature(CODE_RUNNER, workspace)

    def raise_if_deactivated(self, workspace) -> None:
        LicenseHandler.raise_if_workspace_doesnt_have_feature(CODE_RUNNER, workspace)


class CoreXLSFileReaderNodeType(AutomationNodeActionNodeType):
    type = "xls_file_reader"
    model_class = CoreXLSFileReaderActionNode
    service_type = CoreXLSFileReaderServiceType.type

    def get_pytest_params(self, pytest_data_fixture):
        service = pytest_data_fixture.create_enterprise_core_xls_file_reader_service()
        return {"service": service}

    def is_deactivated(self, workspace) -> bool:
        return not LicenseHandler.workspace_has_feature(XLS_FILE_READER, workspace)

    def raise_if_deactivated(self, workspace) -> None:
        LicenseHandler.raise_if_workspace_doesnt_have_feature(
            XLS_FILE_READER, workspace
        )
