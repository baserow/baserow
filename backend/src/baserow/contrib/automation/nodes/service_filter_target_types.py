from typing import Callable, Iterable

from django.contrib.auth.models import AbstractUser

from baserow.contrib.automation.nodes.actions import UpdateAutomationNodeActionType
from baserow.contrib.automation.nodes.exceptions import AutomationNodeDoesNotExist
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.operations import (
    ListAutomationNodeOperationType,
    ReadAutomationNodeOperationType,
    UpdateAutomationNodeOperationType,
)
from baserow.contrib.automation.tools.formulas import (
    InvalidAutomationFormula,
    check_automation_formula,
    check_output_paths,
    previous_node_paths,
)
from baserow.contrib.automation.tools.nodes import output_schema
from baserow.contrib.integrations.local_baserow.service_filters.exceptions import (
    ServiceFilterTargetDoesNotExist,
)
from baserow.contrib.integrations.local_baserow.service_filters.registries import (
    ServiceFilterTargetType,
)
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace


class AutomationNodeServiceFilterTargetType(ServiceFilterTargetType):
    type = "automation_node"
    application_type = "automation"
    read_operation_type = ReadAutomationNodeOperationType.type
    update_operation_type = UpdateAutomationNodeOperationType.type
    list_operation_type = ListAutomationNodeOperationType.type

    def get_owner(self, owner_id: int) -> AutomationNode:
        try:
            node = AutomationNodeHandler().get_node(owner_id)
        except AutomationNodeDoesNotExist as exc:
            raise ServiceFilterTargetDoesNotExist() from exc
        automation = node.workflow.automation
        # Published copies have no workspace, and are changed by publishing again.
        if (
            node.workflow.trashed
            or automation.trashed
            or automation.workspace_id is None
        ):
            raise ServiceFilterTargetDoesNotExist()
        return node

    def get_workspace(self, owner: AutomationNode) -> Workspace:
        return owner.workflow.automation.workspace

    def get_name(self, owner: AutomationNode) -> str:
        return owner.label or owner.get_type().type

    def get_location(self, owner: AutomationNode) -> str:
        return owner.workflow.name

    def list_owners(self, user: AbstractUser, application) -> Iterable[AutomationNode]:
        return CoreHandler().filter_queryset(
            user,
            self.list_operation_type,
            AutomationNode.objects.filter(
                workflow__automation=application, workflow__trashed=False
            )
            .select_related("workflow", "service")
            .order_by("workflow_id", "id"),
            workspace=application.workspace,
        )

    def get_formula_check(
        self, user: AbstractUser, owner: AutomationNode
    ) -> Callable[[str], str | None]:
        # Only the nodes running before this one have produced data it can read.
        # Their outputs are read now: the check may run on another thread, which
        # must not query the database.
        previous_outputs = {
            node.id: output_schema(node) for node in owner.get_previous_points()
        }
        previous_ids = set(previous_outputs)

        def check(formula: str) -> str | None:
            try:
                check_automation_formula("value", formula)
            except InvalidAutomationFormula as exc:
                return exc.error
            for _, _, node_id, _ in previous_node_paths(formula):
                if int(node_id) not in previous_ids:
                    return (
                        f"node {node_id} doesn't run before this node, so its output "
                        "can't be read here."
                    )
            try:
                check_output_paths("value", formula, previous_outputs.get)
            except InvalidAutomationFormula as exc:
                return exc.error
            return None

        return check

    def describe_formula_values(self) -> str:
        return (
            "Filter values can be formulas reading the output of a node running "
            "before this one with get('previous_node.<node_id>.<path>')."
        )

    def persist(self, user, owner, service_type, values) -> None:
        UpdateAutomationNodeActionType.do(user, owner.id, {"service": values})
