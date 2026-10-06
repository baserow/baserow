from typing import Optional

from django.contrib.auth.models import AbstractUser

from baserow.contrib.database.workflow_actions.workflow_action_types import (
    DatabaseWorkflowServiceActionType,
)
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry
from baserow.core.workflow_actions.models import WorkflowAction
from baserow_enterprise.database.workflow_actions.models import (
    CoreRunAgentDatabaseWorkflowAction,
)
from baserow_enterprise.integrations.core.service_types import (
    CoreRunAgentServiceType,
)


class CoreRunAgentWorkflowActionType(DatabaseWorkflowServiceActionType):
    """
    A button that starts a conversation with an agent for the clicked row. The
    click runs as the person clicking, so the conversation belongs to them.
    """

    type = "run_agent"
    model_class = CoreRunAgentDatabaseWorkflowAction
    service_type = CoreRunAgentServiceType.type

    def prepare_values(
        self,
        values: dict,
        user: AbstractUser,
        instance: Optional[WorkflowAction] = None,
    ) -> dict:
        # Copied so the caller's values are left as given.
        service_values = dict(values.get("service") or {})
        if service_values.get("agent_application_id") is not None:
            field = values.get("field") or (instance.field if instance else None)
            # Scoped to the button's workspace here; the service type alone
            # accepts any agent the user may run, in any workspace.
            service_values["agent_application"] = service_type_registry.get(
                self.service_type
            ).get_agent_application_to_run(
                user,
                service_values.pop("agent_application_id"),
                field.table.database.workspace_id if field else None,
            )
            values = {**values, "service": service_values}
        return super().prepare_values(values, user, instance)

    def check_kept_service(self, service: Service, user: AbstractUser, field) -> None:
        super().check_kept_service(service, user, field)
        if service.agent_application_id is not None:
            service_type_registry.get(self.service_type).get_agent_application_to_run(
                user, service.agent_application_id, field.table.database.workspace_id
            )
