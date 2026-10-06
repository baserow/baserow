from django.utils.translation import gettext_lazy as _

from baserow.contrib.automation.nodes.node_types import AutomationNodeActionNodeType
from baserow_enterprise.automation.nodes.models import (
    CoreCodeActionNode,
    CoreRunAgentActionNode,
    CoreXLSFileReaderActionNode,
)
from baserow_enterprise.features import CODE_RUNNER, XLS_FILE_READER
from baserow_enterprise.integrations.core.service_types import (
    CoreCodeServiceType,
    CoreRunAgentServiceType,
    CoreXLSFileReaderServiceType,
)
from baserow_premium.license.handler import LicenseHandler


class CoreCodeNodeType(AutomationNodeActionNodeType):
    type = "code"
    model_class = CoreCodeActionNode
    service_type = CoreCodeServiceType.type
    display_name = _("Code")

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


class CoreRunAgentNodeType(AutomationNodeActionNodeType):
    type = "run_agent"
    model_class = CoreRunAgentActionNode
    service_type = CoreRunAgentServiceType.type
    display_name = _("Run agent")

    def prepare_values(self, values, user, instance=None):
        # Copied so the caller's values are left as given.
        service_values = dict(values.get("service") or {})
        if service_values.get("agent_application_id") is not None:
            workflow = instance.workflow if instance else values.get("workflow")
            # Scoped to the automation's workspace here; the service type
            # alone accepts any agent the user may run, in any workspace.
            service_values["agent_application"] = (
                self.get_service_type().get_agent_application_to_run(
                    user,
                    service_values.pop("agent_application_id"),
                    workflow.automation.workspace_id if workflow else None,
                )
            )
            values = {**values, "service": service_values}
        return super().prepare_values(values, user, instance)

    def get_pytest_params(self, pytest_data_fixture):
        service = pytest_data_fixture.create_enterprise_core_run_agent_service()
        return {"service": service}
