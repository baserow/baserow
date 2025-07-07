from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.node_types import (
    LocalBaserowCreateRowNodeType,
    LocalBaserowDeleteRowNodeType,
    LocalBaserowRowsCreatedNodeTriggerType,
    LocalBaserowUpdateRowNodeType,
)
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.core.services.registries import service_type_registry


class AutomationNodeFixtures:
    def create_automation_node(self, user=None, **kwargs):
        workflow = kwargs.pop("workflow", None)
        if not workflow:
            if user is None:
                user = self.create_user()
            workflow = self.create_automation_workflow(user=user)

        _node_type = kwargs.pop("type", None)
        if _node_type is None:
            node_type = automation_node_type_registry.get("create_row")
        elif isinstance(_node_type, str):
            node_type = automation_node_type_registry.get(_node_type)
        else:
            node_type = _node_type

        if "service" not in kwargs:
            service_kwargs = kwargs.pop("service_kwargs", {})
            service_type = service_type_registry.get(node_type.service_type)
            kwargs["service"] = self.create_service(
                service_type.model_class, **service_kwargs
            )

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

    def create_local_baserow_create_row_action_node(self, user=None, **kwargs):
        return self.create_automation_node(
            user=user,
            type=LocalBaserowCreateRowNodeType.type,
            **kwargs,
        )

    def create_local_baserow_update_row_action_node(self, user=None, **kwargs):
        return self.create_automation_node(
            user=user,
            type=LocalBaserowUpdateRowNodeType.type,
            **kwargs,
        )

    def create_local_baserow_delete_row_action_node(self, user=None, **kwargs):
        return self.create_automation_node(
            user=user,
            type=LocalBaserowDeleteRowNodeType.type,
            **kwargs,
        )
