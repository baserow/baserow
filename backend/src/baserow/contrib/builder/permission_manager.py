from django.contrib.auth import get_user_model

from baserow.contrib.builder.data_sources.operations import (
    DispatchDataSourceOperationType,
    ListDataSourcesPageOperationType,
)
from baserow.contrib.builder.elements.operations import ListElementsPageOperationType
from baserow.contrib.builder.operations import ListPagesBuilderOperationType
from baserow.contrib.builder.workflow_actions.operations import (
    ListBuilderWorkflowActionsPageOperationType,
)
from baserow.core.permission_manager import (
    AllowIfTemplatePermissionManagerType as CoreAllowIfTemplatePermissionManagerType,
)
from baserow.core.registries import PermissionManagerType

User = get_user_model()


class AllowIfTemplatePermissionManagerType(CoreAllowIfTemplatePermissionManagerType):
    """
    Allows read operation on templates.
    """

    BUILDER_OPERATION_ALLOWED_ON_TEMPLATES = [
        ListPagesBuilderOperationType.type,
        ListElementsPageOperationType.type,
        ListBuilderWorkflowActionsPageOperationType.type,
        ListDataSourcesPageOperationType.type,
    ]

    BUILDER_LIVE_OPERATIONS_ON_TEMPLATES = [DispatchDataSourceOperationType.type]

    @property
    def OPERATION_ALLOWED_ON_TEMPLATES(self):
        return (
            self.prev_manager_type.OPERATION_ALLOWED_ON_TEMPLATES
            + self.BUILDER_OPERATION_ALLOWED_ON_TEMPLATES
        )

    @property
    def LIVE_OPERATIONS_ON_TEMPLATES(self):
        return (
            self.prev_manager_type.LIVE_OPERATIONS_ON_TEMPLATES
            + self.BUILDER_LIVE_OPERATIONS_ON_TEMPLATES
        )

    def __init__(self, prev_manager_type: PermissionManagerType):
        self.prev_manager_type = prev_manager_type
