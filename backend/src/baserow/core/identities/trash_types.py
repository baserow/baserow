from django.utils.translation import gettext_lazy as _

from baserow.core.exceptions import TrashItemDoesNotExist
from baserow.core.identities.handler import IdentityHandler
from baserow.core.identities.operations import DeleteIdentityOperationType
from baserow.core.identities.signals import identity_created
from baserow.core.models import UserProfile
from baserow.core.trash.registries import TrashableItemType
from baserow.core.user.identity import is_identity


class IdentityTrashableItemType(TrashableItemType):
    type = "identity"
    model_class = UserProfile

    def get_type_display_name(self):
        return _("identity")

    def lookup_trashed_item(self, trashed_entry, trash_item_lookup_cache=None):
        profile = super().lookup_trashed_item(trashed_entry, trash_item_lookup_cache)
        if not is_identity(profile.user):
            raise TrashItemDoesNotExist()
        return profile

    def trash(self, item_to_trash, requesting_user, trash_entry):
        if not is_identity(item_to_trash.user):
            raise TrashItemDoesNotExist()
        super().trash(item_to_trash, requesting_user, trash_entry)

    def get_parent(self, trashed_item):
        return IdentityHandler.get_workspace(trashed_item.user)

    def get_name(self, trashed_item):
        return trashed_item.user.first_name

    def restore(self, trashed_item, trash_entry):
        super().restore(trashed_item, trash_entry)
        identity_created.send(self, user=None, identity=trashed_item.user)

    def permanently_delete_item(self, trashed_item, trash_item_lookup_cache=None):
        if not is_identity(trashed_item.user):
            raise TrashItemDoesNotExist()
        trashed_item.user.delete()

    def get_restore_operation_type(self):
        return DeleteIdentityOperationType.type

    def get_restore_operation_context(self, trash_entry, trashed_item):
        return IdentityHandler.get_workspace(trashed_item.user)
