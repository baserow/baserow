from abc import ABC

from baserow.contrib.builder.pages.operations import BuilderPageOperationType
from baserow.core.registries import OperationType


class ListBuilderWorkflowActionsPageOperationType(BuilderPageOperationType):
    type = "builder.page.list_workflow_actions"
    object_scope_name = "builder_workflow_action"


class CreateBuilderWorkflowActionOperationType(BuilderPageOperationType):
    type = "builder.page.create_workflow_action"


class OrderBuilderWorkflowActionOperationType(BuilderPageOperationType):
    type = "builder.page.workflow_action.order"


class BuilderWorkflowActionOperationType(OperationType, ABC):
    context_scope_name = "builder_workflow_action"


class DeleteBuilderWorkflowActionOperationType(BuilderWorkflowActionOperationType):
    type = "builder.page.workflow_action.delete"


class UpdateBuilderWorkflowActionOperationType(BuilderWorkflowActionOperationType):
    type = "builder.page.workflow_action.update"


class ReadBuilderWorkflowActionOperationType(BuilderWorkflowActionOperationType):
    type = "builder.page.workflow_action.read"


class RestoreBuilderWorkflowActionOperationType(BuilderWorkflowActionOperationType):
    type = "builder.page.workflow_action.restore"


class DispatchBuilderWorkflowActionOperationType(BuilderWorkflowActionOperationType):
    type = "builder.page.workflow_action.dispatch"
