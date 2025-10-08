from typing import Any, Dict, List, Optional, Union

from django.contrib.auth.models import AbstractUser
from django.db import router
from django.db.models import CharField, Q, QuerySet
from django.db.models.functions import Cast
from django.utils import timezone
from django.utils.translation import gettext as _

from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeMisconfiguredService,
    AutomationNodeNotDeletable,
    AutomationNodeNotReplaceable,
)
from baserow.contrib.automation.nodes.models import (
    AutomationActionNode,
    AutomationNode,
    AutomationTriggerNode,
    CoreHTTPRequestActionNode,
    CoreHTTPTriggerNode,
    CorePeriodicTriggerNode,
    CoreRouterActionNode,
    CoreSMTPEmailActionNode,
    LocalBaserowAggregateRowsActionNode,
    LocalBaserowCreateRowActionNode,
    LocalBaserowDeleteRowActionNode,
    LocalBaserowGetRowActionNode,
    LocalBaserowListRowsActionNode,
    LocalBaserowRowsCreatedTriggerNode,
    LocalBaserowRowsDeletedTriggerNode,
    LocalBaserowRowsUpdatedTriggerNode,
    LocalBaserowUpdateRowActionNode,
)
from baserow.contrib.automation.nodes.registries import AutomationNodeType
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.integrations.core.service_types import (
    CoreHTTPRequestServiceType,
    CoreHTTPTriggerServiceType,
    CorePeriodicServiceType,
    CoreRouterServiceType,
    CoreSMTPEmailServiceType,
)
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowAggregateRowsUserServiceType,
    LocalBaserowDeleteRowServiceType,
    LocalBaserowGetRowUserServiceType,
    LocalBaserowListRowsUserServiceType,
    LocalBaserowRowsCreatedServiceType,
    LocalBaserowRowsDeletedServiceType,
    LocalBaserowRowsUpdatedServiceType,
    LocalBaserowUpsertRowServiceType,
)
from baserow.core.db import specific_iterator
from baserow.core.registry import Instance
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry


class AutomationNodeActionNodeType(AutomationNodeType):
    is_workflow_action = True


class LocalBaserowUpsertRowNodeType(AutomationNodeActionNodeType):
    type = "upsert_row"
    service_type = LocalBaserowUpsertRowServiceType.type

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, int]:
        service = pytest_data_fixture.create_local_baserow_upsert_row_service()
        return {"service": service}


class LocalBaserowCreateRowNodeType(LocalBaserowUpsertRowNodeType):
    type = "create_row"
    model_class = LocalBaserowCreateRowActionNode


class LocalBaserowUpdateRowNodeType(LocalBaserowUpsertRowNodeType):
    type = "update_row"
    model_class = LocalBaserowUpdateRowActionNode


class LocalBaserowDeleteRowNodeType(AutomationNodeActionNodeType):
    type = "delete_row"
    model_class = LocalBaserowDeleteRowActionNode
    service_type = LocalBaserowDeleteRowServiceType.type


class LocalBaserowGetRowNodeType(AutomationNodeActionNodeType):
    type = "get_row"
    model_class = LocalBaserowGetRowActionNode
    service_type = LocalBaserowGetRowUserServiceType.type


class LocalBaserowListRowsNodeType(AutomationNodeActionNodeType):
    type = "list_rows"
    model_class = LocalBaserowListRowsActionNode
    service_type = LocalBaserowListRowsUserServiceType.type


class LocalBaserowAggregateRowsNodeType(AutomationNodeActionNodeType):
    type = "aggregate_rows"
    model_class = LocalBaserowAggregateRowsActionNode
    service_type = LocalBaserowAggregateRowsUserServiceType.type


class CoreHttpRequestNodeType(AutomationNodeActionNodeType):
    type = "http_request"
    model_class = CoreHTTPRequestActionNode
    service_type = CoreHTTPRequestServiceType.type


class CoreSMTPEmailNodeType(AutomationNodeActionNodeType):
    type = "smtp_email"
    model_class = CoreSMTPEmailActionNode
    service_type = CoreSMTPEmailServiceType.type


class CoreRouterActionNodeType(AutomationNodeActionNodeType):
    type = "router"
    model_class = CoreRouterActionNode
    service_type = CoreRouterServiceType.type

    # Routers cannot be moved in the workflow to a new position.
    is_fixed = True

    def get_output_nodes(
        self, node: CoreRouterActionNode, specific: bool = False
    ) -> Union[List[AutomationActionNode], QuerySet[AutomationActionNode]]:
        """
        Given a router node, this method returns the output nodes that are
        along the edges of the router node.
        :param node: The router node instance.
        :param specific: Whether to return the specific node instances.
        :return: An iterable of output nodes that are connected to the
            router node's edges.
        """

        queryset = (
            node.workflow.automation_workflow_nodes.select_related("content_type")
            .filter(previous_node_id=node.id)
            .filter(
                Q(previous_node_output="")
                | Q(
                    previous_node_output__in=node.service.specific.edges.values_list(
                        Cast("uid", output_field=CharField()), flat=True
                    )
                ),
            )
        )
        return specific_iterator(queryset) if specific else queryset

    def before_delete(self, node: CoreRouterActionNode):
        output_nodes_count = self.get_output_nodes(node).count()
        if output_nodes_count != 0:
            raise AutomationNodeNotDeletable(
                "Router nodes cannot be deleted if they "
                "have one or more output nodes associated with them."
            )

    def before_replace(self, node: CoreRouterActionNode, new_node_type: Instance):
        output_nodes_count = self.get_output_nodes(node).count()
        if output_nodes_count != 0:
            raise AutomationNodeNotReplaceable(
                "Router nodes cannot be replaced if they "
                "have one or more output nodes associated with them."
            )

    def after_create(self, node: CoreRouterActionNode):
        """
        After a router node is created, this method will create
        an initial edge for the user to start with.

        :param node: The router node instance that was just created.
        """

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

        if instance:
            service = instance.service.specific
            prepared_uids = [edge["uid"] for edge in values["service"].get("edges", [])]
            persisted_uids = [str(edge.uid) for edge in service.edges.only("uid")]
            removed_uids = list(set(persisted_uids) - set(prepared_uids))
            output_nodes_with_removed_uids = AutomationNode.objects.filter(
                previous_node_id=instance.id, previous_node_output__in=removed_uids
            ).exists()
            if output_nodes_with_removed_uids:
                raise AutomationNodeMisconfiguredService(
                    "One or more branches have been removed from the router node, "
                    "but they still point to output nodes. These nodes must be "
                    "trashed before the router can be updated."
                )
        return super().prepare_values(values, user, instance)


class AutomationNodeTriggerType(AutomationNodeType):
    # Triggers cannot be moved in the workflow to a new position.
    is_fixed = True

    is_workflow_trigger = True

    def after_register(self):
        service_type_registry.get(self.service_type).start_listening(self.on_event)
        return super().after_register()

    def before_unregister(self):
        service_type_registry.get(self.service_type).stop_listening()
        return super().before_unregister()

    def before_delete(self, node: AutomationTriggerNode):
        """
        Trigger nodes cannot be deleted.
        :param node: The node instance to check.
        :raises: AutomationNodeNotDeletable
        """

        raise AutomationNodeNotDeletable(
            "Triggers can not be created, deleted or duplicated, "
            "they can only be replaced with a different type."
        )

    def on_event(
        self,
        services: QuerySet[Service],
        event_payload: Optional[List[Dict]] = None,
        user: Optional[AbstractUser] = None,
    ):
        from baserow.contrib.automation.workflows.handler import (
            AutomationWorkflowHandler,
        )

        triggers = (
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

        for trigger in triggers:
            workflow = trigger.workflow

            AutomationWorkflowHandler().async_start_workflow(
                workflow,
                event_payload,
            )

            # We don't want subsequent events to trigger a new test run
            AutomationWorkflowHandler().reset_workflow_temporary_states(workflow)


class LocalBaserowRowsCreatedNodeTriggerType(AutomationNodeTriggerType):
    type = "rows_created"
    model_class = LocalBaserowRowsCreatedTriggerNode
    service_type = LocalBaserowRowsCreatedServiceType.type


class LocalBaserowRowsUpdatedNodeTriggerType(AutomationNodeTriggerType):
    type = "rows_updated"
    model_class = LocalBaserowRowsUpdatedTriggerNode
    service_type = LocalBaserowRowsUpdatedServiceType.type


class LocalBaserowRowsDeletedNodeTriggerType(AutomationNodeTriggerType):
    type = "rows_deleted"
    model_class = LocalBaserowRowsDeletedTriggerNode
    service_type = LocalBaserowRowsDeletedServiceType.type


class CorePeriodicTriggerNodeType(
    AutomationNodeTriggerType,
):
    type = "periodic"
    model_class = CorePeriodicTriggerNode
    service_type = CorePeriodicServiceType.type


class CoreHTTPTriggerNodeType(AutomationNodeTriggerType):
    type = "http_trigger"
    model_class = CoreHTTPTriggerNode
    service_type = CoreHTTPTriggerServiceType.type
