from typing import Any, Callable, Dict, Iterable, Optional

from django.contrib.auth.models import AbstractUser
from django.db import router
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeFirstNodeMustBeTrigger,
    AutomationNodeMisconfiguredService,
    AutomationNodeNotDeletable,
    AutomationNodeNotMovable,
    AutomationNodeNotReplaceable,
    AutomationNodeTriggerAlreadyExists,
    AutomationNodeTriggerMustBeFirstNode,
)
from baserow.contrib.automation.nodes.models import (
    AIAgentActionNode,
    AutomationNode,
    AutomationTriggerNode,
    CoreCSVFileReaderActionNode,
    CoreGotoActionNode,
    CoreHTTPRequestActionNode,
    CoreHTTPTriggerNode,
    CoreIteratorActionNode,
    CoreManualTriggerNode,
    CorePeriodicTriggerNode,
    CoreRouterActionNode,
    CoreSMTPEmailActionNode,
    CoreStartWorkflowActionNode,
    LocalBaserowAggregateRowsActionNode,
    LocalBaserowCreateRowActionNode,
    LocalBaserowCreateRowsActionNode,
    LocalBaserowDeleteRowActionNode,
    LocalBaserowFieldsUpdatedTriggerNode,
    LocalBaserowGetRowActionNode,
    LocalBaserowListRowsActionNode,
    LocalBaserowRowsCreatedTriggerNode,
    LocalBaserowRowsDeletedTriggerNode,
    LocalBaserowRowsUpdatedTriggerNode,
    LocalBaserowUpdateRowActionNode,
    LocalBaserowUpdateRowsActionNode,
    SlackWriteMessageActionNode,
)
from baserow.contrib.automation.nodes.registries import AutomationNodeType
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.integrations.ai.service_types import AIAgentServiceType
from baserow.contrib.integrations.core.service_types import (
    CoreCSVFileReaderServiceType,
    CoreGotoServiceType,
    CoreHTTPRequestServiceType,
    CoreHTTPTriggerServiceType,
    CoreIteratorServiceType,
    CoreManualTriggerServiceType,
    CorePeriodicServiceType,
    CoreRouterServiceType,
    CoreSMTPEmailServiceType,
    CoreStartWorkflowServiceType,
)
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowAggregateRowsUserServiceType,
    LocalBaserowCreateRowsServiceType,
    LocalBaserowDeleteRowServiceType,
    LocalBaserowFieldsUpdatedServiceType,
    LocalBaserowGetRowUserServiceType,
    LocalBaserowListRowsUserServiceType,
    LocalBaserowRowsCreatedServiceType,
    LocalBaserowRowsDeletedServiceType,
    LocalBaserowRowsUpdatedServiceType,
    LocalBaserowUpdateRowsServiceType,
    LocalBaserowUpsertRowServiceType,
)
from baserow.contrib.integrations.slack.service_types import (
    SlackWriteMessageServiceType,
)
from baserow.core.graph.types import GraphPointPositionType
from baserow.core.registry import Instance
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry
from baserow.core.services.types import DispatchResult


def validate_goto_destination(
    source_node: AutomationNode,
    destination_node: Optional[AutomationNode],
) -> Optional[str]:
    """
    Validates that destination_node is an eligible "Go to node" destination
    for source_node.

    A destination is eligible when it belongs to the same workflow, is at the
    same level (i.e. has the same parent/container nodes), is not a trigger node
    and runs before the Go to node (a backward jump). A node may not target
    itself.
    """

    if destination_node is None:
        return None

    if destination_node.id == source_node.id:
        return _("The destination node cannot be the Go to node itself.")

    if destination_node.workflow_id != source_node.workflow_id:
        return _("The destination node must belong to the same workflow.")

    if destination_node.get_type().is_workflow_trigger:
        return _("The destination node cannot be a trigger node.")

    source_level = sorted(node.id for node in source_node.get_parent_points())
    destination_level = sorted(node.id for node in destination_node.get_parent_points())
    if source_level != destination_level:
        return _("The destination node must be at the same level as the Go to node.")

    # Only backward jumps are allowed: the destination must be one of the nodes
    # that run before the Go to node. A forward jump would skip the nodes between
    # the Go to node and its destination, leaving them unexecuted, so any later
    # node that reads a skipped node's output via the previous-node data provider
    # would fail.
    previous_node_ids = {node.id for node in source_node.get_previous_points()}
    if destination_node.id not in previous_node_ids:
        return _(
            "The destination node must run before the Go to node. "
            "Jumping forward is not allowed."
        )

    return None


class AutomationNodeActionNodeType(AutomationNodeType):
    is_workflow_action = True

    def before_create(self, workflow, reference_node, position, output):
        if reference_node is None:
            raise AutomationNodeFirstNodeMustBeTrigger()

    def before_move(self, node, reference_node, position, output):
        if reference_node is None:
            raise AutomationNodeFirstNodeMustBeTrigger()


class ContainerNodeTypeMixin:
    is_container = True

    def before_delete(self, node: "ContainerNodeTypeMixin"):
        if node.workflow.get_graph().get_children(node):
            raise AutomationNodeNotDeletable(
                "Container nodes cannot be deleted if they "
                "have one or more children nodes associated with them."
            )

    def before_replace(self, node: "ContainerNodeTypeMixin", new_node_type: Instance):
        if node.workflow.get_graph().get_children(node):
            raise AutomationNodeNotReplaceable(
                "Container nodes cannot be replaced if they "
                "have one or more children nodes associated with them."
            )

        super().before_replace(node, new_node_type)

    def before_move(
        self,
        node: "ContainerNodeTypeMixin",
        reference_node: AutomationNode | None,
        position: GraphPointPositionType,
        output: str,
    ):
        """
        Check the container node is not moved inside itself.
        """

        if node in reference_node.get_parent_points():
            raise AutomationNodeNotMovable(
                "A container node cannot be moved inside itself"
            )

        super().before_move(node, reference_node, position, output)


class LocalBaserowUpsertRowNodeType(AutomationNodeActionNodeType):
    type = "local_baserow_upsert_row"
    compat_type = "upsert_row"
    service_type = LocalBaserowUpsertRowServiceType.type

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, int]:
        service = pytest_data_fixture.create_local_baserow_upsert_row_service()
        return {"service": service}


class LocalBaserowCreateRowNodeType(LocalBaserowUpsertRowNodeType):
    display_name = _("Local Baserow create row")
    type = "local_baserow_create_row"
    compat_type = "create_row"
    model_class = LocalBaserowCreateRowActionNode


class LocalBaserowCreateRowsNodeType(AutomationNodeActionNodeType):
    type = "local_baserow_create_rows"
    model_class = LocalBaserowCreateRowsActionNode
    service_type = LocalBaserowCreateRowsServiceType.type

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, int]:
        service = pytest_data_fixture.create_local_baserow_create_rows_service()
        return {"service": service}


class LocalBaserowUpdateRowNodeType(LocalBaserowUpsertRowNodeType):
    display_name = _("Local Baserow update row")
    type = "local_baserow_update_row"
    compat_type = "update_row"
    model_class = LocalBaserowUpdateRowActionNode


class LocalBaserowUpdateRowsNodeType(AutomationNodeActionNodeType):
    type = "local_baserow_update_rows"
    model_class = LocalBaserowUpdateRowsActionNode
    service_type = LocalBaserowUpdateRowsServiceType.type

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, int]:
        service = pytest_data_fixture.create_local_baserow_update_rows_service()
        return {"service": service}


class LocalBaserowDeleteRowNodeType(AutomationNodeActionNodeType):
    display_name = _("Local Baserow delete row")
    type = "local_baserow_delete_row"
    compat_type = "delete_row"
    model_class = LocalBaserowDeleteRowActionNode
    service_type = LocalBaserowDeleteRowServiceType.type


class LocalBaserowGetRowNodeType(AutomationNodeActionNodeType):
    display_name = _("Local Baserow get row")
    type = "local_baserow_get_row"
    compat_type = "get_row"
    model_class = LocalBaserowGetRowActionNode
    service_type = LocalBaserowGetRowUserServiceType.type


class LocalBaserowListRowsNodeType(AutomationNodeActionNodeType):
    display_name = _("Local Baserow list rows")
    type = "local_baserow_list_rows"
    compat_type = "list_rows"
    model_class = LocalBaserowListRowsActionNode
    service_type = LocalBaserowListRowsUserServiceType.type


class LocalBaserowAggregateRowsNodeType(AutomationNodeActionNodeType):
    display_name = _("Local Baserow aggregate rows")
    type = "local_baserow_aggregate_rows"
    compat_type = "aggregate_rows"
    model_class = LocalBaserowAggregateRowsActionNode
    service_type = LocalBaserowAggregateRowsUserServiceType.type


class CoreHttpRequestNodeType(AutomationNodeActionNodeType):
    display_name = _("HTTP request")
    type = "http_request"
    model_class = CoreHTTPRequestActionNode
    service_type = CoreHTTPRequestServiceType.type


class CoreIteratorNodeType(ContainerNodeTypeMixin, AutomationNodeActionNodeType):
    display_name = _("Iterator")
    type = "iterator"
    model_class = CoreIteratorActionNode
    service_type = CoreIteratorServiceType.type


class CoreCSVFileReaderNodeType(AutomationNodeActionNodeType):
    type = "csv_file_reader"
    model_class = CoreCSVFileReaderActionNode
    service_type = CoreCSVFileReaderServiceType.type


class CoreSMTPEmailNodeType(AutomationNodeActionNodeType):
    display_name = _("Send email")
    type = "smtp_email"
    model_class = CoreSMTPEmailActionNode
    service_type = CoreSMTPEmailServiceType.type


class CoreStartWorkflowNodeType(AutomationNodeActionNodeType):
    type = "start_workflow"
    model_class = CoreStartWorkflowActionNode
    service_type = CoreStartWorkflowServiceType.type


class AIAgentActionNodeType(AutomationNodeActionNodeType):
    display_name = _("AI agent")
    type = "ai_agent"
    model_class = AIAgentActionNode
    service_type = AIAgentServiceType.type


class CoreRouterActionNodeType(AutomationNodeActionNodeType):
    display_name = _("Router")
    type = "router"
    model_class = CoreRouterActionNode
    service_type = CoreRouterServiceType.type

    def has_node_on_edge(self, node: CoreRouterActionNode) -> bool:
        """
        Given a router node, this method returns whether one of its edges has a node.

        :param node: The router node instance.
        """

        for edge_uid in node.service.get_type().get_edges(node.service.specific).keys():
            if edge_uid != "" and node.workflow.get_graph().get_next_points(
                node, edge_uid
            ):
                return True

        return False

    def before_delete(self, node: CoreRouterActionNode):
        if self.has_node_on_edge(node):
            raise AutomationNodeNotDeletable(
                "Router nodes cannot be deleted if they "
                "have one or more output nodes associated with them."
            )

        super().before_delete(node)

    def before_replace(self, node: CoreRouterActionNode, new_node_type: Instance):
        if self.has_node_on_edge(node):
            raise AutomationNodeNotReplaceable(
                "Router nodes cannot be replaced if they "
                "have one or more output nodes associated with them."
            )

        super().before_replace(node, new_node_type)

    def before_move(
        self,
        node: AutomationTriggerNode,
        reference_node: AutomationNode | None,
        position: GraphPointPositionType,
        output: str,
    ):
        """
        Check the container node is not moved inside it self.
        """

        if self.has_node_on_edge(node):
            raise AutomationNodeNotMovable(
                "Router nodes cannot be moved if they "
                "have one or more output nodes associated with them."
            )

        super().before_move(node, reference_node, position, output)

    def after_create(self, node: CoreRouterActionNode):
        """
        After a router node is created, this method will create
        an initial edge for the user to start with.

        :param node: The router node instance that was just created.
        """

        if not len(node.service.edges.all()):
            node.service.edges.create(label=_("Branch"))

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: AutomationNode = None,
    ) -> Dict[str, Any]:
        """
        Before updating a router node's service, this method is called to allow us to
        check if one or more edges have been removed. If so, we need to verify that
        there are no automation node outputs pointing to those edges. If there are,
        then an exception is raised to prevent the update.

        :param values: The values to prepare for the router node.
        :param user: The user performing the action.
        :param instance: The current instance of the router node.
        :return: The prepared values for the router node.
        """

        service_values = values.get("service", {})
        if instance and "edges" in service_values:
            prepared_uids = [
                str(edge["uid"]) for edge in service_values.get("edges", [])
            ]
            service = instance.service.specific
            persisted_uids = [str(edge.uid) for edge in service.edges.only("uid")]
            removed_uids = list(set(persisted_uids) - set(prepared_uids))

            for removed_uid in removed_uids:
                if instance.workflow.get_graph().get_point_at_position(
                    instance, "south", removed_uid
                ):
                    raise AutomationNodeMisconfiguredService(
                        "One or more branches have been removed from the router node, "
                        "but they still point to output nodes. These nodes must be "
                        "trashed before the router can be updated."
                    )

        return super().prepare_values(values, user, instance)


class CoreGotoActionNodeType(AutomationNodeActionNodeType):
    type = "goto_node"
    model_class = CoreGotoActionNode
    service_type = CoreGotoServiceType.type

    def dispatch(self, automation_node, dispatch_context) -> DispatchResult:
        """
        Applies the automation-graph rules on top of the generic goto service
        dispatch. The service only resolves the intent to jump (and to which
        destination); this node type owns the graph-specific decisions:

        - While simulating, the jump is never followed, to avoid looping the
          simulated path. Execution then continues to the natural next node.
        - Before a real jump is followed, the destination is re-validated
          against the live graph, so a link that became invalid after the
          service was configured (e.g. the destination was moved to another
          level) raises a clean misconfigured error instead of jumping.
        """

        from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

        dispatch_result = super().dispatch(automation_node, dispatch_context)

        if dispatch_result.output_node_id is None:
            return dispatch_result

        if getattr(dispatch_context, "simulate_until_node", None) is not None:
            dispatch_result.output_node_id = None
            return dispatch_result

        destination_node = AutomationNodeHandler().get_node(
            dispatch_result.output_node_id
        )
        if error := validate_goto_destination(automation_node, destination_node):
            raise ServiceImproperlyConfiguredDispatchException(error)

        return dispatch_result

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: AutomationNode = None,
    ) -> Dict[str, Any]:
        """
        Validates the configured destination node before the service is updated.

        The destination must be a same-level, non-trigger node of the same
        workflow, and cannot be the Go to node itself. We can only check this
        when updating an existing node, as the source node must already exist
        in the graph to determine its level.
        """

        from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

        service_values = values.get("service", {})
        if instance is not None and service_values.get("destination_node_id"):
            destination_node = AutomationNodeHandler().get_node(
                service_values["destination_node_id"]
            )
            if error := validate_goto_destination(instance, destination_node):
                raise AutomationNodeMisconfiguredService(error)

        return super().prepare_values(values, user, instance)


class AutomationNodeTriggerType(AutomationNodeType):
    is_workflow_trigger = True

    def after_register(self):
        service_type_registry.get(self.service_type).start_listening(self.on_event)
        return super().after_register()

    def before_unregister(self):
        service_type_registry.get(self.service_type).stop_listening()
        return super().before_unregister()

    def before_create(
        self,
        workflow: AutomationWorkflow,
        reference_node: AutomationNode,
        position: str,
        output: str,
    ):
        if workflow.get_graph().get_point_at_position(None, "south", ""):
            raise AutomationNodeTriggerAlreadyExists()

        if reference_node is not None:
            raise AutomationNodeTriggerMustBeFirstNode()

    def before_delete(self, node: AutomationNode):
        if node.workflow.get_graph().get_next_points(node):
            raise AutomationNodeNotDeletable(
                "Trigger nodes cannot be deleted if they are followed nodes."
            )

    def before_move(
        self,
        node: AutomationTriggerNode,
        reference_node: AutomationNode | None,
        position: GraphPointPositionType,
        output: str,
    ):
        raise AutomationNodeNotMovable("Trigger nodes cannot be moved.")

    def on_event(
        self,
        services: Iterable[Service],
        event_payload: Dict | None | Callable = None,
        user: Optional[AbstractUser] = None,
    ):
        from baserow.contrib.automation.workflows.handler import (
            AutomationWorkflowHandler,
        )

        triggers = list(
            self.model_class.objects.filter(
                service__in=services,
            )
            .using(router.db_for_write(self.model_class))
            .filter(
                Q(
                    Q(workflow__state=WorkflowState.LIVE)
                    | Q(workflow__allow_test_run_until__gte=timezone.now())
                    | Q(workflow__simulate_until_node__isnull=False)
                ),
            )
            .select_related("workflow__automation__workspace")
        )

        # For perf reasons, store the trigger<->service relationship.
        service_map = {service.id: service for service in services}

        for trigger in triggers:
            # If we've received a callable payload, call it with the specific service,
            # this can give us a payload that is specific to the trigger's service.
            service_payload = (
                event_payload(service_map[trigger.service_id])
                if callable(event_payload)
                else event_payload
            )

            workflow = trigger.workflow
            AutomationWorkflowHandler().async_start_workflow(
                workflow,
                service_payload,
            )

            # We don't want subsequent events to trigger a new test run
            AutomationWorkflowHandler().reset_workflow_temporary_states(workflow)


class LocalBaserowRowsCreatedNodeTriggerType(AutomationNodeTriggerType):
    display_name = _("Local Baserow rows created")
    type = "local_baserow_rows_created"
    compat_type = "rows_created"
    model_class = LocalBaserowRowsCreatedTriggerNode
    service_type = LocalBaserowRowsCreatedServiceType.type


class LocalBaserowRowsUpdatedNodeTriggerType(AutomationNodeTriggerType):
    display_name = _("Local Baserow rows updated")
    type = "local_baserow_rows_updated"
    compat_type = "rows_updated"
    model_class = LocalBaserowRowsUpdatedTriggerNode
    service_type = LocalBaserowRowsUpdatedServiceType.type


class LocalBaserowRowsDeletedNodeTriggerType(AutomationNodeTriggerType):
    display_name = _("Local Baserow rows deleted")
    type = "local_baserow_rows_deleted"
    compat_type = "rows_deleted"
    model_class = LocalBaserowRowsDeletedTriggerNode
    service_type = LocalBaserowRowsDeletedServiceType.type


class LocalBaserowFieldsUpdatedNodeTriggerType(AutomationNodeTriggerType):
    type = "local_baserow_fields_updated"
    model_class = LocalBaserowFieldsUpdatedTriggerNode
    service_type = LocalBaserowFieldsUpdatedServiceType.type


class CorePeriodicTriggerNodeType(
    AutomationNodeTriggerType,
):
    display_name = _("Periodic trigger")
    type = "periodic"
    model_class = CorePeriodicTriggerNode
    service_type = CorePeriodicServiceType.type


class CoreHTTPTriggerNodeType(AutomationNodeTriggerType):
    display_name = _("HTTP trigger")
    type = "http_trigger"
    model_class = CoreHTTPTriggerNode
    service_type = CoreHTTPTriggerServiceType.type


class CoreManualTriggerNodeType(AutomationNodeTriggerType):
    type = "manual"
    model_class = CoreManualTriggerNode
    service_type = CoreManualTriggerServiceType.type


class SlackWriteMessageActionNodeType(AutomationNodeActionNodeType):
    display_name = _("Slack write message")
    type = "slack_write_message"
    model_class = SlackWriteMessageActionNode
    service_type = SlackWriteMessageServiceType.type
