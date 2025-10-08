import dataclasses

from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import (
    AutomationActionNode,
    AutomationNode,
    CoreRouterActionNode,
    LocalBaserowCreateRowActionNode,
)
from baserow.contrib.automation.nodes.node_types import (
    CoreHTTPTriggerNodeType,
    CorePeriodicTriggerNodeType,
    CoreRouterActionNodeType,
    LocalBaserowCreateRowNodeType,
    LocalBaserowDeleteRowNodeType,
    LocalBaserowRowsCreatedNodeTriggerType,
    LocalBaserowUpdateRowNodeType,
)
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.integrations.core.models import CoreRouterServiceEdge
from baserow.core.services.registries import service_type_registry


@dataclasses.dataclass
class CoreRouterWithEdges:
    router: CoreRouterActionNode
    edge1: CoreRouterServiceEdge
    edge1_output: AutomationActionNode
    edge2: CoreRouterServiceEdge
    edge2_output: AutomationNode
    fallback_output_node: AutomationActionNode


class AutomationNodeFixtures:
    def create_automation_node(self, user=None, **kwargs):
        workflow = kwargs.pop("workflow", None)
        if not workflow:
            if user is None:
                user = self.create_user()
            workflow = self.create_automation_workflow(user)

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

    def create_local_baserow_create_row_action_node(
        self, user=None, **kwargs
    ) -> LocalBaserowCreateRowActionNode:
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

    def create_core_router_action_node(
        self, user=None, **kwargs
    ) -> CoreRouterActionNode:
        return self.create_automation_node(
            user=user,
            type=CoreRouterActionNodeType.type,
            **kwargs,
        )

    def create_core_router_action_node_with_edges(self, user=None, **kwargs):
        service = self.create_core_router_service(default_edge_label="Default")
        router = self.create_core_router_action_node(
            user=user, service=service, **kwargs
        )
        workflow = router.workflow
        edge1 = self.create_core_router_service_edge(
            service=service, label="Do this", condition="'true'"
        )
        edge1_output = workflow.automation_workflow_nodes.get(
            previous_node_output=edge1.uid
        ).specific
        edge2 = self.create_core_router_service_edge(
            service=service, label="Do that", condition="'true'"
        )
        edge2_output = workflow.automation_workflow_nodes.get(
            previous_node_output=edge2.uid
        ).specific
        fallback_output_node = self.create_local_baserow_create_row_action_node(
            workflow=workflow, previous_node_id=router.id, previous_node_output=""
        )

        return CoreRouterWithEdges(
            router=router,
            edge1=edge1,
            edge1_output=edge1_output,
            edge2=edge2,
            edge2_output=edge2_output,
            fallback_output_node=fallback_output_node,
        )

    def create_periodic_trigger_node(self, user=None, **kwargs):
        return self.create_automation_node(
            user=user,
            type=CorePeriodicTriggerNodeType.type,
            **kwargs,
        )

    def create_http_trigger_node(self, user=None, **kwargs):
        return self.create_automation_node(
            user=user,
            type=CoreHTTPTriggerNodeType.type,
            **kwargs,
        )
