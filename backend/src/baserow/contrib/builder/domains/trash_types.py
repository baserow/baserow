from typing import Any, Optional

from baserow.contrib.builder.domains.models import Domain
from baserow.contrib.builder.domains.operations import RestoreDomainOperationType
from baserow.core.models import TrashEntry
from baserow.core.trash.registries import TrashableItemType

from .signals import domain_created


class DomainTrashableItemType(TrashableItemType):
    type = "builder_domain"
    model_class = Domain

    def get_parent(self, trashed_item: Any) -> Optional[Any]:
        return trashed_item.builder

    def get_name(self, trashed_item: Domain) -> str:
        return trashed_item.domain_name

    def restore(self, trashed_item: Domain, trash_entry: TrashEntry):
        super().restore(trashed_item, trash_entry)
        domain_created.send(
            self,
            domain=trashed_item,
            user=None,
        )

    def permanently_delete_item(
        self, trashed_item: Domain, trash_item_lookup_cache=None
    ):
        """
        Deletes a domain.
        """

        trashed_item.delete()

    def get_restore_operation_type(self) -> str:
        return RestoreDomainOperationType.type
