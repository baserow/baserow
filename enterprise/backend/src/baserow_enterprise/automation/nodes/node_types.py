from django.utils.translation import gettext_lazy as _

from baserow.contrib.automation.nodes.node_types import AutomationActionNodeType
from baserow_enterprise.automation.nodes.models import (
    CoreCodeActionNode,
    CoreXLSFileReaderActionNode,
    LocalBaserowSemanticSearchActionNode,
)
from baserow_enterprise.features import CODE_RUNNER, XLS_FILE_READER
from baserow_enterprise.integrations.core.service_types import (
    CoreCodeServiceType,
    CoreXLSFileReaderServiceType,
)
from baserow_enterprise.integrations.local_baserow.service_types import (
    LocalBaserowSemanticSearchServiceType,
)
from baserow_premium.license.handler import LicenseHandler


class CoreCodeActionNodeType(AutomationActionNodeType):
    type = "code"
    model_class = CoreCodeActionNode
    service_type = CoreCodeServiceType.type
    display_name = _("Code")

    def is_deactivated(self, workspace) -> bool:
        return not LicenseHandler.workspace_has_feature(CODE_RUNNER, workspace)

    def raise_if_deactivated(self, workspace) -> None:
        LicenseHandler.raise_if_workspace_doesnt_have_feature(CODE_RUNNER, workspace)


class CoreXLSFileReaderActionNodeType(AutomationActionNodeType):
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


class LocalBaserowSemanticSearchActionNodeType(AutomationActionNodeType):
    type = "local_baserow_semantic_search"
    model_class = LocalBaserowSemanticSearchActionNode
    service_type = LocalBaserowSemanticSearchServiceType.type

    def get_pytest_params(self, pytest_data_fixture):
        service = pytest_data_fixture.create_local_baserow_semantic_search_service()
        return {"service": service}

    def is_deactivated(self, workspace) -> bool:
        return self.get_service_type().is_deactivated(workspace)

    def raise_if_deactivated(self, workspace) -> None:
        self.get_service_type().raise_if_deactivated(workspace)
