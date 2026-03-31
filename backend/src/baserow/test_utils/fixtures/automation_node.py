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
    LocalBaserowGetRowNodeType,
    LocalBaserowRowsCreatedNodeTriggerType,
    LocalBaserowUpdateRowNodeType,
)
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.workflows.constants import WorkflowState
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

    def create_local_baserow_get_row_action_node(self, user=None, **kwargs):
        return self.create_automation_node(
            user=user,
            type=LocalBaserowGetRowNodeType.type,
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

    def iterator_graph_fixture(self, create_after_iteration_node: bool = True):
        """
        Fixture that creates the following graph:
        - trigger_node
            - iterator_node
                - iterator_child_1
                - iterator_child_2
            - after_iteration_node

        trigger sample data are
        [
            {"Name": "Apple", "Color": "Red"},
            {"Name": "Banana", "Color": "Yellow"},
        ]
        """

        user = self.create_user()

        trigger_table, trigger_table_fields, _ = self.build_table(
            user=user,
            columns=[("Name", "text"), ("Color", "text")],
            rows=[],
        )
        iterator_child_1_table, iterator_child_1_table_fields, _ = self.build_table(
            user=user,
            columns=[("Name", "text")],
            rows=[],
        )
        iterator_child_2_table, iterator_child_2_table_fields, _ = self.build_table(
            user=user,
            columns=[("Name", "text")],
            rows=[],
        )
        after_iteration_table, after_iteration_table_fields, _ = self.build_table(
            user=user,
            columns=[("Name", "text")],
            rows=[],
        )

        integration = self.create_local_baserow_integration(user=user)

        workflow = self.create_automation_workflow(
            user=user,
            state=WorkflowState.LIVE,
            trigger_type="local_baserow_rows_created",
            trigger_service_kwargs={
                "table": trigger_table,
                "integration": integration,
                "sample_data": {
                    "data": {
                        "results": [
                            {
                                trigger_table_fields[0].name: "Apple",
                                trigger_table_fields[1].name: "Red",
                            },
                            {
                                trigger_table_fields[0].name: "Banana",
                                trigger_table_fields[1].name: "Yellow",
                            },
                        ]
                    }
                },
            },
        )

        trigger = workflow.get_trigger()

        iterator_node = self.create_core_iterator_action_node(
            workflow=workflow,
            reference_node=trigger,
            position="south",
            output="",
            service_kwargs={
                "source": f'get("previous_node.{trigger.id}")',
                "integration": integration,
            },
        )

        iterator_child_1_node = self.create_local_baserow_create_row_action_node(
            workflow=workflow,
            reference_node=iterator_node,
            position="child",
            output="",
            label="First iterator child",
            service_kwargs={
                "table": iterator_child_1_table,
                "integration": integration,
            },
        )
        iterator_child_1_node.service.specific.field_mappings.create(
            field=iterator_child_1_table_fields[0],
            value=f'get("current_iteration.{iterator_node.id}.item.{trigger_table_fields[0].name}")',
        )

        iterator_child_2_node = self.create_local_baserow_create_row_action_node(
            workflow=workflow,
            reference_node=iterator_child_1_node,
            position="south",
            output="",
            label="Second iterator child",
            service_kwargs={
                "table": iterator_child_2_table,
                "integration": integration,
            },
        )
        iterator_child_2_node.service.specific.field_mappings.create(
            field=iterator_child_2_table_fields[0],
            value=f'get("current_iteration.{iterator_node.id}.item.{trigger_table_fields[1].name}")',
        )

        if create_after_iteration_node:
            after_iteration_node = self.create_local_baserow_create_row_action_node(
                workflow=workflow,
                reference_node=iterator_node,
                position="south",
                output="",
                label="After iterator",
                service_kwargs={
                    "table": after_iteration_table,
                    "integration": integration,
                },
            )
            after_iteration_node.service.specific.field_mappings.create(
                field=after_iteration_table_fields[0],
                value=f'get("previous_node.{iterator_node.id}.*.{trigger_table_fields[0].name}")',
            )
        else:
            after_iteration_node = None

        return {
            "workflow": workflow,
            "trigger_node": trigger,
            "trigger_table": trigger_table,
            "trigger_table_fields": trigger_table_fields,
            "iterator_node": iterator_node,
            "iterator_child_1_node": iterator_child_1_node,
            "iterator_child_1_table": iterator_child_1_table,
            "iterator_child_1_table_fields": iterator_child_1_table_fields,
            "iterator_child_2_node": iterator_child_2_node,
            "iterator_child_2_table": iterator_child_2_table,
            "iterator_child_2_table_fields": iterator_child_2_table_fields,
            "after_iteration_node": after_iteration_node,
            "after_iteration_table": after_iteration_table,
            "after_iteration_table_fields": after_iteration_table_fields,
        }

    def nested_iterator_graph_fixture(self, create_after_iteration_node: bool = True):
        """
        Fixture that creates the following graph:
        - trigger_node
            - parent_iterator_node
                - child_iterator_node
                    - child_iterator_child_1
                    - child_iterator_child_2
            - after_iteration_node

        trigger sample data are
        [
            {
                "Name": "Apple",
                "Items": [
                    {"Name": "Fuji", "Color": "Red"},
                    {"Name": "Granny Smith", "Color": "Green"},
                ],
            },
            {
                "Name": "Banana",
                "Items": [
                    {"Name": "Cavendish", "Color": "Yellow"},
                    {"Name": "Plantain", "Color": "Green"},
                ],
            },
        ]
        """

        user = self.create_user()

        trigger_table, trigger_table_fields, _ = self.build_table(
            user=user,
            columns=[("Name", "text"), ("Items", "text")],
            rows=[],
        )
        child_iterator_child_1_table, child_iterator_child_1_table_fields, _ = (
            self.build_table(
                user=user,
                columns=[("Name", "text")],
                rows=[],
            )
        )
        child_iterator_child_2_table, child_iterator_child_2_table_fields, _ = (
            self.build_table(
                user=user,
                columns=[("Color", "text")],
                rows=[],
            )
        )
        after_iteration_table, after_iteration_table_fields, _ = self.build_table(
            user=user,
            columns=[("Name", "text")],
            rows=[],
        )

        integration = self.create_local_baserow_integration(user=user)

        workflow = self.create_automation_workflow(
            user=user,
            state=WorkflowState.LIVE,
            trigger_type="local_baserow_rows_created",
            trigger_service_kwargs={
                "table": trigger_table,
                "integration": integration,
                "sample_data": {
                    "data": {
                        "results": [
                            {
                                trigger_table_fields[0].name: "Apple",
                                trigger_table_fields[1].name: [
                                    {"Name": "Fuji", "Color": "Red"},
                                    {"Name": "Granny Smith", "Color": "Green"},
                                ],
                            },
                            {
                                trigger_table_fields[0].name: "Banana",
                                trigger_table_fields[1].name: [
                                    {"Name": "Cavendish", "Color": "Yellow"},
                                    {"Name": "Plantain", "Color": "Green"},
                                ],
                            },
                        ]
                    }
                },
            },
        )

        trigger = workflow.get_trigger()

        parent_iterator_node = self.create_core_iterator_action_node(
            workflow=workflow,
            reference_node=trigger,
            position="south",
            output="",
            service_kwargs={
                "source": f'get("previous_node.{trigger.id}")',
                "integration": integration,
            },
        )

        child_iterator_node = self.create_core_iterator_action_node(
            workflow=workflow,
            reference_node=parent_iterator_node,
            position="child",
            output="",
            service_kwargs={
                "source": f'get("current_iteration.{parent_iterator_node.id}.item.{trigger_table_fields[1].name}")',
                "integration": integration,
            },
        )

        child_iterator_child_1_node = self.create_local_baserow_create_row_action_node(
            workflow=workflow,
            reference_node=child_iterator_node,
            position="child",
            output="",
            label="First child iterator child",
            service_kwargs={
                "table": child_iterator_child_1_table,
                "integration": integration,
            },
        )
        child_iterator_child_1_node.service.specific.field_mappings.create(
            field=child_iterator_child_1_table_fields[0],
            value=f'get("current_iteration.{child_iterator_node.id}.item.Name")',
        )

        child_iterator_child_2_node = self.create_local_baserow_create_row_action_node(
            workflow=workflow,
            reference_node=child_iterator_child_1_node,
            position="south",
            output="",
            label="Second child iterator child",
            service_kwargs={
                "table": child_iterator_child_2_table,
                "integration": integration,
            },
        )
        child_iterator_child_2_node.service.specific.field_mappings.create(
            field=child_iterator_child_2_table_fields[0],
            value=f'get("previous_node.{child_iterator_child_1_node.id}.{child_iterator_child_1_table_fields[0].db_column}")',
        )

        if create_after_iteration_node:
            after_iteration_node = self.create_local_baserow_create_row_action_node(
                workflow=workflow,
                reference_node=parent_iterator_node,
                position="south",
                output="",
                label="After parent iterator",
                service_kwargs={
                    "table": after_iteration_table,
                    "integration": integration,
                },
            )
            after_iteration_node.service.specific.field_mappings.create(
                field=after_iteration_table_fields[0],
                value=f'get("previous_node.{parent_iterator_node.id}.*.{trigger_table_fields[0].name}")',
            )
        else:
            after_iteration_node = None

        return {
            "workflow": workflow,
            "trigger_node": trigger,
            "trigger_table": trigger_table,
            "trigger_table_fields": trigger_table_fields,
            "parent_iterator_node": parent_iterator_node,
            "child_iterator_node": child_iterator_node,
            "child_iterator_child_1_node": child_iterator_child_1_node,
            "child_iterator_child_1_table": child_iterator_child_1_table,
            "child_iterator_child_1_table_fields": child_iterator_child_1_table_fields,
            "child_iterator_child_2_node": child_iterator_child_2_node,
            "child_iterator_child_2_table": child_iterator_child_2_table,
            "child_iterator_child_2_table_fields": child_iterator_child_2_table_fields,
            "after_iteration_node": after_iteration_node,
            "after_iteration_table": after_iteration_table,
            "after_iteration_table_fields": after_iteration_table_fields,
        }
