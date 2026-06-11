from typing import Dict

from baserow.contrib.builder.workflow_actions.workflow_action_types import (
    BuilderWorkflowServiceActionType,
)
from baserow_enterprise.builder.workflow_actions.models import (
    CoreCodeWorkflowAction,
    CoreXLSFileReaderWorkflowAction,
)
from baserow_enterprise.features import CODE_RUNNER, XLS_FILE_READER
from baserow_enterprise.integrations.core.service_types import (
    CoreCodeServiceType,
    CoreXLSFileReaderServiceType,
)
from baserow_premium.license.handler import LicenseHandler


class CoreCodeActionType(BuilderWorkflowServiceActionType):
    type = "code"
    model_class = CoreCodeWorkflowAction
    service_type = CoreCodeServiceType.type

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, int]:
        service = pytest_data_fixture.create_enterprise_core_code_service()
        return {"service": service}

    def is_deactivated(self, workspace) -> bool:
        return not LicenseHandler.workspace_has_feature(CODE_RUNNER, workspace)

    def raise_if_deactivated(self, workspace) -> None:
        LicenseHandler.raise_if_workspace_doesnt_have_feature(CODE_RUNNER, workspace)


class CoreXLSFileReaderActionType(BuilderWorkflowServiceActionType):
    type = "xls_file_reader"
    model_class = CoreXLSFileReaderWorkflowAction
    service_type = CoreXLSFileReaderServiceType.type

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, int]:
        service = pytest_data_fixture.create_enterprise_core_xls_file_reader_service()
        return {"service": service}

    def is_deactivated(self, workspace) -> bool:
        return not LicenseHandler.workspace_has_feature(XLS_FILE_READER, workspace)

    def raise_if_deactivated(self, workspace) -> None:
        LicenseHandler.raise_if_workspace_doesnt_have_feature(
            XLS_FILE_READER, workspace
        )
