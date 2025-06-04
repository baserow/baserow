from typing import Dict, Optional

from django.db.models import QuerySet

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.nodes.models import (
    LocalBaserowCreateRowActionNode,
    LocalBaserowRowsCreatedTriggerNode,
    LocalBaserowRowsDeletedTriggerNode,
    LocalBaserowRowsUpdatedTriggerNode,
)
from baserow.contrib.automation.nodes.registries import (
    AutomationNodeActionNodeType,
    AutomationNodeType,
)
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowRowsCreatedTriggerServiceType,
    LocalBaserowRowsDeletedTriggerServiceType,
    LocalBaserowRowsUpdatedTriggerServiceType,
    LocalBaserowUpsertRowServiceType,
)
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry


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
    def on_event(
        self, service_queryset: QuerySet[Service], event_payload: Optional[Dict] = None
    ):
        triggers = (
            self.model_class.objects.filter(
                service__in=service_queryset, workflow__published=True
            )
            .select_related("workflow__automation__workspace")
            .all()
        )

        for trigger in triggers:
            AutomationWorkflowHandler().run_workflow(
                trigger.workflow,
                AutomationDispatchContext(trigger.workflow, event_payload),
            )

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
