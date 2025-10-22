import dataclasses

from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import (
    AutomationActionNode,
    AutomationNode,
    CoreIteratorActionNode,
    CoreRouterActionNode,
    LocalBaserowCreateRowActionNode,
)
from baserow.contrib.automation.nodes.node_types import (
    CoreHTTPTriggerNodeType,
    CoreIteratorNodeType,
    CorePeriodicTriggerNodeType,
    CoreRouterActionNodeType,
    LocalBaserowCreateRowNodeType,
    LocalBaserowDeleteRowNodeType,
    LocalBaserowRowsCreatedNodeTriggerType,
    LocalBaserowUpdateRowNodeType,
)
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.integrations.core.models import CoreRouterServiceEdge
from baserow.core.cache import local_cache
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
        _node_type = kwargs.pop("type", None)
        if _node_type is None:
            node_type = automation_node_type_registry.get("create_row")
        elif isinstance(_node_type, str):
            node_type = automation_node_type_registry.get(_node_type)
        else:
            node_type = _node_type

        workflow = kwargs.pop("workflow", None)
        if not workflow:
            if user is None:
                user = self.create_user()
            workflow = self.create_automation_workflow(
                user, create_trigger=not node_type.is_workflow_trigger
            )

        if "service" not in kwargs:
            service_kwargs = kwargs.pop("service_kwargs", {})
            service_type = service_type_registry.get(node_type.service_type)
            kwargs["service"] = self.create_service(
                service_type.model_class, **service_kwargs
            )

        [
            last_reference_node,
            last_position,
            last_output,
        ] = workflow.get_graph().get_last_position()

        # By default the node is placed at the end of the graph if not position is
        # provided
        reference_node = kwargs.pop("reference_node", last_reference_node)
        position = kwargs.pop("position", last_position)
        output = kwargs.pop("output", last_output)

        with local_cache.context():  # We make sure the cache is empty
            created_node = AutomationNodeHandler().create_node(
                node_type, workflow=workflow, **kwargs
            )
            # insert the node in the graph
            workflow.get_graph().insert(created_node, reference_node, position, output)

        return created_node

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

    def create_core_iterator_action_node(
        self, user=None, **kwargs
    ) -> CoreIteratorActionNode:
        return self.create_automation_node(
            user=user,
            type=CoreIteratorNodeType.type,
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
            service=service,
            label="Do this",
            condition="'true'",
            output_label="output edge 1",
        )
        edge2 = self.create_core_router_service_edge(
            service=service,
            label="Do that",
            condition="'true'",
            output_label="output edge 2",
        )

        edge1_output = workflow.get_graph().get_node_at_position(
            reference_node=router, position="south", output=edge1.uid
        )
        edge2_output = workflow.get_graph().get_node_at_position(
            reference_node=router, position="south", output=edge2.uid
        )

        fallback_output_node = self.create_local_baserow_create_row_action_node(
            workflow=workflow, reference_node=router, label="fallback node"
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
