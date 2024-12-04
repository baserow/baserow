from abc import ABC

from baserow.core.registries import OperationType


class DashboardOperationType(OperationType, ABC):
    context_scope_name = "dashboard"
