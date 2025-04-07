from abc import ABCMeta

from baserow.core.registries import OperationType


class AutomationOperationType(OperationType, metaclass=ABCMeta):
    context_scope_name = "automation"


class ListAutomationWorkflowsOperationType(AutomationOperationType):
    type = "automation.list_workflows"


class OrderAutomationWorkflowsOperationType(AutomationOperationType):
    type = "automation.order_workflows"
