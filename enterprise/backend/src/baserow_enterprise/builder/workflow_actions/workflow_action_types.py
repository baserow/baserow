from typing import Dict

from baserow.contrib.builder.workflow_actions.workflow_action_types import (
    BuilderWorkflowServiceActionType,
)
from baserow.core.import_export.untrusted_content import UntrustedContentTypeMixin
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow_enterprise.builder.workflow_actions.models import (
    CoreCodeWorkflowAction,
    CoreXLSFileReaderWorkflowAction,
    MicrosoftOutlookSendEmailWorkflowAction,
    MicrosoftTeamsWriteMessageWorkflowAction,
)
from baserow_enterprise.features import (
    CODE_RUNNER,
    MICROSOFT_OUTLOOK,
    MICROSOFT_TEAMS,
    XLS_FILE_READER,
)
from baserow_enterprise.integrations.core.service_types import (
    CoreCodeServiceType,
    CoreXLSFileReaderServiceType,
)
from baserow_enterprise.integrations.microsoft_outlook.service_types import (
    MicrosoftOutlookSendEmailServiceType,
)
from baserow_enterprise.integrations.microsoft_teams.service_types import (
    MicrosoftTeamsWriteMessageServiceType,
)
from baserow_premium.license.handler import LicenseHandler


class CoreCodeActionType(UntrustedContentTypeMixin, BuilderWorkflowServiceActionType):
    def get_import_report_entry(self, instance):
        return {
            "type": "builder_code_action",
            "id": instance.id,
            "page_id": instance.page_id,
            "page_name": instance.page.name,
            "element_id": instance.element_id,
        }

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

    def dispatch(self, workflow_action, dispatch_context):
        if workflow_action.page.builder.untrusted_content:
            raise ServiceImproperlyConfiguredDispatchException(
                "Custom code is disabled until the application content is trusted."
            )
        return super().dispatch(workflow_action, dispatch_context)


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


class MicrosoftTeamsWriteMessageActionType(BuilderWorkflowServiceActionType):
    type = "microsoft_teams_write_message"
    model_class = MicrosoftTeamsWriteMessageWorkflowAction
    service_type = MicrosoftTeamsWriteMessageServiceType.type

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, int]:
        service = pytest_data_fixture.create_microsoft_teams_write_message_service()
        return {"service": service}

    def is_deactivated(self, workspace) -> bool:
        return not LicenseHandler.workspace_has_feature(MICROSOFT_TEAMS, workspace)

    def raise_if_deactivated(self, workspace) -> None:
        LicenseHandler.raise_if_workspace_doesnt_have_feature(
            MICROSOFT_TEAMS, workspace
        )


class MicrosoftOutlookSendEmailActionType(BuilderWorkflowServiceActionType):
    type = "microsoft_outlook_send_email"
    model_class = MicrosoftOutlookSendEmailWorkflowAction
    service_type = MicrosoftOutlookSendEmailServiceType.type

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, int]:
        service = pytest_data_fixture.create_microsoft_outlook_send_email_service()
        return {"service": service}

    def is_deactivated(self, workspace) -> bool:
        return not LicenseHandler.workspace_has_feature(MICROSOFT_OUTLOOK, workspace)

    def raise_if_deactivated(self, workspace) -> None:
        LicenseHandler.raise_if_workspace_doesnt_have_feature(
            MICROSOFT_OUTLOOK, workspace
        )
