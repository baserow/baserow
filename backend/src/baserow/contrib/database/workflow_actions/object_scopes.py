from typing import Optional

from django.db.models import Q, QuerySet

from baserow.contrib.database.fields.object_scopes import FieldObjectScopeType
from baserow.contrib.database.object_scopes import DatabaseObjectScopeType
from baserow.contrib.database.table.object_scopes import DatabaseTableObjectScopeType
from baserow.contrib.database.workflow_actions.models import DatabaseWorkflowAction
from baserow.core.object_scopes import (
    ApplicationObjectScopeType,
    WorkspaceObjectScopeType,
)
from baserow.core.registries import ObjectScopeType, object_scope_type_registry


class DatabaseWorkflowActionObjectScopeType(ObjectScopeType):
    type = "database_workflow_action"
    model_class = DatabaseWorkflowAction

    def get_parent_scope(self) -> Optional["ObjectScopeType"]:
        return object_scope_type_registry.get_by_type(FieldObjectScopeType)

    def get_base_queryset(self, include_trash: bool = False) -> QuerySet:
        return (
            super()
            .get_base_queryset(include_trash)
            .filter(field__table__database__workspace__isnull=False)
        )

    def get_enhanced_queryset(self, include_trash: bool = False) -> QuerySet:
        return self.get_base_queryset(include_trash).select_related(
            "field__table__database__workspace"
        )

    def get_filter_for_scope_type(self, scope_type, scopes):
        if scope_type.type == WorkspaceObjectScopeType.type:
            return Q(field__table__database__workspace__in=[s.id for s in scopes])

        if (
            scope_type.type == DatabaseObjectScopeType.type
            or scope_type.type == ApplicationObjectScopeType.type
        ):
            return Q(field__table__database__in=[s.id for s in scopes])

        if scope_type.type == DatabaseTableObjectScopeType.type:
            return Q(field__table__in=[s.id for s in scopes])

        if scope_type.type == FieldObjectScopeType.type:
            return Q(field__in=[s.id for s in scopes])

        if scope_type.type == self.type:
            return Q(id__in=[s.id for s in scopes])

        raise TypeError("The given type is not handled.")
