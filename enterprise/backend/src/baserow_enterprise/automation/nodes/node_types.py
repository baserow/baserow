from django.utils.translation import gettext_lazy as _

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.nodes.node_types import (
    AutomationActionNodeType,
    AutomationTriggerNodeType,
    LocalBaserowTableNodeTypeMixin,
)
from baserow.core.import_export.untrusted_content import UntrustedContentTypeMixin
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow_enterprise.automation.nodes.models import (
    CoreCodeActionNode,
    CoreXLSFileReaderActionNode,
    LocalBaserowRowCommentPostedTriggerNode,
    LocalBaserowSemanticSearchActionNode,
)
from baserow_enterprise.features import CODE_RUNNER, XLS_FILE_READER
from baserow_enterprise.integrations.core.service_types import (
    CoreCodeServiceType,
    CoreXLSFileReaderServiceType,
)
from baserow_enterprise.integrations.local_baserow.service_types import (
    LocalBaserowRowCommentPostedTriggerServiceType,
    LocalBaserowSemanticSearchServiceType,
)
from baserow_enterprise.license.row_comment_tools import RowCommentToolLicense
from baserow_premium.license.handler import LicenseHandler


class CoreCodeActionNodeType(UntrustedContentTypeMixin, AutomationActionNodeType):
    def get_import_report_entry(self, instance):
        return {
            "type": "automation_code_node",
            "id": instance.id,
            "label": instance.label,
            "workflow_id": instance.workflow_id,
        }

    type = "code"
    model_class = CoreCodeActionNode
    service_type = CoreCodeServiceType.type
    display_name = _("Code")

    def is_deactivated(self, workspace) -> bool:
        return not LicenseHandler.workspace_has_feature(CODE_RUNNER, workspace)

    def raise_if_deactivated(self, workspace) -> None:
        LicenseHandler.raise_if_workspace_doesnt_have_feature(CODE_RUNNER, workspace)

    def dispatch(self, automation_node, dispatch_context):
        if automation_node.workflow.untrusted_content:
            raise ServiceImproperlyConfiguredDispatchException(
                "Custom code is disabled until the workflow content is trusted."
            )
        return super().dispatch(automation_node, dispatch_context)


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


class LocalBaserowRowCommentPostedTriggerNodeType(
    RowCommentToolLicense, LocalBaserowTableNodeTypeMixin, AutomationTriggerNodeType
):
    type = LocalBaserowRowCommentPostedTriggerServiceType.type
    display_name = _("Row comment is posted")
    service_type = type
    model_class = LocalBaserowRowCommentPostedTriggerNode

    def _start_workflow(self, trigger, service, event_payload):
        service_type = self.get_service_type()
        context = AutomationDispatchContext(trigger.workflow, history=None)
        try:
            subject = service_type.get_acting_user(service, context)
        except ServiceImproperlyConfiguredDispatchException:
            return None
        if not service_type.can_subject_read(service, subject, context.workspace):
            return None
        payload = event_payload(service) if callable(event_payload) else event_payload
        if not service_type.matches_event(service, subject, payload):
            return None
        return super()._start_workflow(trigger, service, payload)
