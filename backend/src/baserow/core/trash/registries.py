from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional

from baserow.core.exceptions import TrashItemDoesNotExist
from baserow.core.registry import (
    Instance,
    ModelInstanceMixin,
    ModelRegistryMixin,
    Registry,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class TrashableItemType(ModelInstanceMixin, Instance, ABC):
    """
    A TrashableItemType specifies a baserow model which can be trashed.
    """

    def lookup_trashed_item(
        self, trashed_entry, trash_item_lookup_cache: Dict[str, Any] = None
    ):
        """
        Returns the actual instance of the trashed item. By default simply does a get
        on the model_class's trash manager.

        :param trash_item_lookup_cache: A dictionary which can be used to store
            expensive objects used to lookup this item which could be re-used when
            looking up other items of this type.
        :param trashed_entry: The entry to get the real trashed instance for.
        :return: An instance of the model_class with trashed_item_id
        """

        try:
            return self.model_class.trash.get(id=trashed_entry.trash_item_id)
        except self.model_class.DoesNotExist:
            raise TrashItemDoesNotExist()

    @abstractmethod
    def permanently_delete_item(
        self,
        trashed_item: Any,
        trash_item_lookup_cache: Dict[str, Any] = None,
    ):
        """
        Should be implemented to actually delete the specified trashed item from the
        database and do any other required clean-up.

        :param trashed_item: The item to delete permanently.
        :param trash_item_lookup_cache: If a cache is being used to speed up trash
            item lookups it should be provided here so trash items can invalidate the
            cache if when they are deleted a potentially cache item becomes invalid.
        """

        pass

    @property
    def requires_parent_id(self) -> bool:
        """
        :returns True if this trash type requires a parent id to lookup a specific item,
            false if only the trash_item_id is required to perform a lookup.
        """

        return False

    @abstractmethod
    def get_parent(self, trashed_item: Any) -> Optional[Any]:
        """
        Returns the parent for this item.

        :param trashed_item: The item to lookup a parent for.
        :returns Either the parent item or None if this item has no parent.
        """

        pass

    @abstractmethod
    def restore(self, trashed_item: Any, trash_entry):
        """
        Called when a trashed item should be restored. Will set trashed to true and
        save. Should be overridden if additional actions such as restoring related
        items or web socket signals are needed.

        :param trash_entry: The trash entry that was restored from.
        :param trashed_item: The item that to be restored.
        """

        trashed_item.trashed = False
        trashed_item.save(update_fields=["trashed"])

    @abstractmethod
    def get_name(self, trashed_item: Any) -> str:
        """
        Should return the name of this particular trashed item to display in the trash
        modal.

        :param trashed_item: The item to be named.
        :return The name of the trashed_item
        """

        pass

    def get_names(self, trashed_item: Any) -> str:
        """
        Should return an array of names of this particular trashed item to display in
        the trash modal. This is typically used when multiple items have been deleted
        in batch and can be visualized differently by the client.

        :param trashed_item: The item to be named.
        :return The names of the trashed_item.
        """

        pass

    def trash(self, item_to_trash: Any, requesting_user, trash_entry):
        """
        Saves trashed=True on the provided item and should be overridden to
        perform any other cleanup and trashing other items related to
        item_to_trash.

        :param item_to_trash: The item to be trashed.
        :param requesting_user: The user who is trashing the item.
        :param trash_entry: The trash entry useful to save additional data like
            some related items.
        """

        item_to_trash.trashed = True
        item_to_trash.save(update_fields=["trashed"])

    @abstractmethod
    def get_restore_operation_type(
        self,
    ) -> str:
        """
        Returns the operation type used to check permissions for deleting an object
        of this type.
        """

        pass

    def get_restore_operation_context(self, trash_entry, trashed_item) -> str:
        """
        Returns the context to use when checking permission for restoring an item
        of this type.
        """

        return trashed_item

    def get_owner(self, trashed_item: Any) -> Optional["AbstractUser"]:
        return None


class TrashableItemTypeRegistry(ModelRegistryMixin, Registry):
    """
    The TrashableItemTypeRegistry contains models which can be "trashed" in baserow.
    When an instance of a trashable model is trashed it is removed from baserow but
    not permanently. Once trashed an item can then be restored to add it back to
    baserow just as it was when it was trashed.
    """

    name = "trashable"


trash_item_type_registry = TrashableItemTypeRegistry()
