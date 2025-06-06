from typing import Dict, List, Optional

from django.contrib.auth.models import AbstractUser
from django.db.models import Q, QuerySet
from django.utils import timezone

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.nodes.models import (
    AutomationActionNode,
    LocalBaserowCreateRowActionNode,
    LocalBaserowRowsCreatedTriggerNode,
    LocalBaserowRowsDeletedTriggerNode,
    LocalBaserowRowsUpdatedTriggerNode,
)
from baserow.contrib.automation.nodes.registries import AutomationNodeType
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowRowsCreatedTriggerServiceType,
    LocalBaserowRowsDeletedTriggerServiceType,
    LocalBaserowRowsUpdatedTriggerServiceType,
    LocalBaserowUpsertRowServiceType,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry
from baserow.core.services.types import DispatchResult


class AutomationNodeActionNodeType(AutomationNodeType):
    is_workflow_action = True

    def dispatch(
        self,
        automation_node: AutomationActionNode,
        dispatch_context: AutomationDispatchContext,
    ) -> DispatchResult:
        return ServiceHandler().dispatch_service(
            automation_node.service.specific, dispatch_context
        )


class LocalBaserowUpsertRowNodeType(AutomationNodeActionNodeType):
    type = "upsert_row"
    service_type = LocalBaserowUpsertRowServiceType.type

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, int]:
        service = pytest_data_fixture.create_local_baserow_upsert_row_service()
        return {"service": service}


class LocalBaserowCreateRowNodeType(LocalBaserowUpsertRowNodeType):
    type = "create_row"
    model_class = LocalBaserowCreateRowActionNode


class AutomationNodeTriggerType(AutomationNodeType):
    is_workflow_trigger = True

    def on_event(
        self,
        service_queryset: QuerySet[Service],
        event_payload: Optional[List[Dict]] = None,
        user: Optional[AbstractUser] = None,
    ):
        from baserow.contrib.automation.workflows.service import (
            AutomationWorkflowService,
        )

        workflow_service = AutomationWorkflowService()
        now = timezone.now()

        triggers = (
            self.model_class.objects.filter(
                service__in=service_queryset,
            )
            .filter(
                Q(
                    Q(workflow__published=True)
                    | Q(workflow__allow_test_run_until__gte=now)
                ),
            )
            .select_related("workflow__automation__workspace")
        )

        for trigger in triggers:
            workflow = trigger.workflow
            workflow_service.run_workflow(
                workflow.id,
                event_payload,
                user=user,
            )
            if workflow.allow_test_run_until:
                workflow.allow_test_run_until = None
                workflow.save(updated_fields=["allow_test_run_until"])

    def after_register(self):
        service_type_registry.get(self.service_type).start_listening(self.on_event)
        return super().after_register()

    def before_unregister(self):
        service_type_registry.get(self.service_type).stop_listening()
        return super().before_unregister()


class LocalBaserowRowsCreatedNodeTriggerType(AutomationNodeTriggerType):
    type = "rows_created"
    model_class = LocalBaserowRowsCreatedTriggerNode
    service_type = LocalBaserowRowsCreatedTriggerServiceType.type


class LocalBaserowRowsUpdatedNodeTriggerType(AutomationNodeTriggerType):
    type = "rows_updated"
    model_class = LocalBaserowRowsUpdatedTriggerNode
    service_type = LocalBaserowRowsUpdatedTriggerServiceType.type


class LocalBaserowRowsDeletedNodeTriggerType(AutomationNodeTriggerType):
    type = "rows_deleted"
    model_class = LocalBaserowRowsDeletedTriggerNode
    service_type = LocalBaserowRowsDeletedTriggerServiceType.type
