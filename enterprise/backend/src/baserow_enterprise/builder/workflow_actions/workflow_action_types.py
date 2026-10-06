from typing import Dict

from baserow.contrib.builder.workflow_actions.workflow_action_types import (
    BuilderWorkflowServiceActionType,
)
from baserow.core.services.registries import service_type_registry
from baserow_enterprise.builder.workflow_actions.models import (
    CoreCodeWorkflowAction,
    CoreRunAgentWorkflowAction,
    CoreXLSFileReaderWorkflowAction,
)
from baserow_enterprise.features import CODE_RUNNER, XLS_FILE_READER
from baserow_enterprise.integrations.core.service_types import (
    CoreCodeServiceType,
    CoreRunAgentServiceType,
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


class CoreRunAgentActionType(BuilderWorkflowServiceActionType):
    """
    Starts an agent conversation from a published application. Always queued:
    a visitor's click must not wait tens of seconds on a model, so the result
    only carries the conversation link.
    """

    type = "run_agent"
    model_class = CoreRunAgentWorkflowAction
    service_type = CoreRunAgentServiceType.type

    def prepare_values(self, values, user, instance=None):
        if values.get("service") is not None:
            # Copied so the caller's values are left as given.
            service_values = dict(values["service"])
            service_values["wait_for_result"] = False
            if service_values.get("agent_application_id") is not None:
                page = values.get("page") or (instance.page if instance else None)
                service_values["agent_application"] = service_type_registry.get(
                    self.service_type
                ).get_agent_application_to_run(
                    user,
                    service_values.pop("agent_application_id"),
                    page.builder.workspace_id if page else None,
                )
            values = {**values, "service": service_values}
        return super().prepare_values(values, user, instance)

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, int]:
        service = pytest_data_fixture.create_enterprise_core_run_agent_service()
        return {"service": service}
