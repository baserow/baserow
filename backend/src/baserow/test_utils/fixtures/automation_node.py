from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.node_types import (
    LocalBaserowRowsCreatedNodeTriggerType,
)
from baserow.contrib.automation.nodes.registries import automation_node_type_registry


class AutomationNodeFixtures:
    def create_automation_node(self, user=None, **kwargs):
        workflow = kwargs.pop("workflow", None)
        if not workflow:
            if user is None:
                user = self.create_user()
            workflow = self.create_automation_workflow(user=user)

        _node_type = kwargs.pop("node_type", None)
        if _node_type is None:
            node_type = automation_node_type_registry.get("rows_created")
        elif isinstance(_node_type, str):
            node_type = automation_node_type_registry.get(_node_type)
        else:
            node_type = _node_type

        if "order" not in kwargs:
            kwargs["order"] = AutomationNode.get_last_order(workflow)

        return AutomationNodeHandler().create_node(
            node_type, workflow=workflow, **kwargs
        )

    def create_local_baserow_rows_created_trigger_node(self, user=None, **kwargs):
        service = kwargs.pop("service", None)
        if service is None:
            service = self.create_local_baserow_rows_created_service()
        return self.create_automation_node(
            user=user,
            service=service,
            node_type=LocalBaserowRowsCreatedNodeTriggerType.type,
            **kwargs,
        )
