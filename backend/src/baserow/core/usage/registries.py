from abc import ABC, abstractmethod

from baserow.core.registry import Instance, Registry

UsageInMB = int
USAGE_UNIT_MB = 1000**2


class WorkspaceStorageUsageItemType(Instance, ABC):
    """
    A GroupStorageUsageItemType defines an item that can calculate
    the usage of a group in a specific part of the application
    """

    def calculate_storage_usage_instance(self):
        """
        Calculates the storage usage for the whole instance. Can be used to update
        instance wide related usage changes.
        """

        pass

    @abstractmethod
    def calculate_storage_usage_workspace(self, workspace_id: int) -> UsageInMB:
        """
        Calculates the storage usage for a workspace in a specific part of the
        application

        :param workspace_id: the group that the usage is calculated for
        :return: the total usage
        """

        pass


class WorkspaceStorageUsageItemTypeRegistry(Registry):
    """
    A trash_item_type_registry contains all the different usage calculations
    that should be called when the total usage of a group is
    calculated
    """

    name = "usage"


workspace_storage_usage_item_registry = WorkspaceStorageUsageItemTypeRegistry()
