from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.node_types import (
    AutomationNodeTriggerType,
    LocalBaserowRowsCreatedNodeTriggerType,
)
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowRowsCreated,
    LocalBaserowUpsertRow,
)


class AutomationNodeFixtures:
    def create_automation_node(self, user=None, **kwargs):
        workflow = kwargs.pop("workflow", None)
        if not workflow:
            if user is None:
                user = self.create_user()
            workflow = self.create_automation_workflow(user=user)

        _node_type = kwargs.pop("type", None)
        if _node_type is None:
            node_type = automation_node_type_registry.get("rows_created")
        elif isinstance(_node_type, str):
            node_type = automation_node_type_registry.get(_node_type)
        else:
            node_type = _node_type

        if "service" not in kwargs:
            service_kwargs = kwargs.pop("service_kwargs", {})
            service_model = LocalBaserowUpsertRow
            if issubclass(node_type.__class__, AutomationNodeTriggerType):
                service_model = LocalBaserowRowsCreated
            kwargs["service"] = self.create_service(service_model, **service_kwargs)

        if "order" not in kwargs:
            kwargs["order"] = AutomationNode.get_last_order(workflow)

        return AutomationNodeHandler().create_node(
            node_type, workflow=workflow, **kwargs
        )

    def create_local_baserow_rows_created_trigger_node(self, user=None, **kwargs):
        return self.create_automation_node(
            user=user,
            type=LocalBaserowRowsCreatedNodeTriggerType.type,
            **kwargs,
        )
