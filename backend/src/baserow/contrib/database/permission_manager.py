from django.contrib.auth import get_user_model

from baserow.contrib.database.fields.operations import ListFieldsOperationType
from baserow.contrib.database.operations import ListTablesDatabaseTableOperationType
from baserow.contrib.database.rows.operations import ReadDatabaseRowOperationType
from baserow.contrib.database.table.operations import ListRowsDatabaseTableOperationType
from baserow.contrib.database.views.operations import (
    ListAggregationsViewOperationType,
    ListViewDecorationOperationType,
    ListViewsOperationType,
    ReadAggregationsViewOperationType,
    ReadViewFieldOptionsOperationType,
    ReadViewOperationType,
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

    DATABASE_OPERATION_ALLOWED_ON_TEMPLATES = [
        ListTablesDatabaseTableOperationType.type,
        ListFieldsOperationType.type,
        ListRowsDatabaseTableOperationType.type,
        ListViewsOperationType.type,
        ReadDatabaseRowOperationType.type,
        ReadViewOperationType.type,
        ReadViewFieldOptionsOperationType.type,
        ListViewDecorationOperationType.type,
        ListAggregationsViewOperationType.type,
        ReadAggregationsViewOperationType.type,
    ]

    @property
    def OPERATION_ALLOWED_ON_TEMPLATES(self):
        return (
            self.prev_manager_type.OPERATION_ALLOWED_ON_TEMPLATES
            + self.DATABASE_OPERATION_ALLOWED_ON_TEMPLATES
        )

    @property
    def LIVE_OPERATIONS_ON_TEMPLATES(self):
        return self.prev_manager_type.LIVE_OPERATIONS_ON_TEMPLATES

    def __init__(self, prev_manager_type: PermissionManagerType):
        self.prev_manager_type = prev_manager_type
