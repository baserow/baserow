from django.db import transaction
from django.db.transaction import Atomic

from baserow.core.exceptions import ApplicationOperationNotSupported
from baserow.core.models import SharedApplication
from baserow.core.registries import ApplicationType


class SharedApplicationType(ApplicationType):
    """
    The hidden application of a workspace that owns its workspace integrations.
    Baserow keeps one per workspace: nobody creates, renames, duplicates, deletes,
    snapshots or exports it, and the frontend doesn't show it. Its integrations
    travel in exports as copies owned by the applications that use them.
    """

    type = "shared"
    model_class = SharedApplication
    supports_snapshots = False
    supports_integrations = True
    is_user_managed = False

    def supports_integration_type(self, integration_type) -> bool:
        """Every integration type, so that any application can use it."""

        return True

    def export_safe_transaction_context(self, application: SharedApplication) -> Atomic:
        return transaction.atomic()

    def create_application(self, *args, **kwargs) -> SharedApplication:
        raise ApplicationOperationNotSupported()

    def export_serialized(self, *args, **kwargs):
        raise ApplicationOperationNotSupported()

    def import_serialized(self, *args, **kwargs) -> SharedApplication:
        raise ApplicationOperationNotSupported()
