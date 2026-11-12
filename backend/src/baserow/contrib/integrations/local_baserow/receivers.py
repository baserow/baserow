from django.dispatch import receiver

from baserow.contrib.database.table.signals import table_schema_changed
from baserow.contrib.integrations.local_baserow.models import LocalBaserowIntegration
from baserow.core.cache import global_cache, local_cache
from baserow.core.models import UserProfile
from baserow.core.signals import user_permanently_deleted
from baserow.core.trash.signals import before_permanently_deleted


@receiver(table_schema_changed)
def invalidate_table_cache(sender, table_id, **kwargs):
    # Invalidate local cache when the table schema is updated
    global_cache.invalidate(invalidate_key=f"table_{table_id}__service_invalidate_key")
    local_cache.delete(f"integration_service_{table_id}_table_model")


def _clear_authorized_subject(subject_type, subject_id):
    """Invalidate integrations whose canonical authorization was deleted."""

    LocalBaserowIntegration.objects.filter(
        authorized_subject_type=subject_type,
        authorized_subject_id=subject_id,
    ).update(authorized_subject_type=None, authorized_subject_id=None)


@receiver(user_permanently_deleted)
def clear_permanently_deleted_user_authorization(sender, user_id, **kwargs):
    """Retain integrations but invalidate those authorized by a deleted user."""

    _clear_authorized_subject("auth.User", user_id)


@receiver(before_permanently_deleted)
def clear_permanently_deleted_identity_authorization(sender, trash_item, **kwargs):
    """Retain integrations when an identity is permanently deleted from trash."""

    if (
        isinstance(trash_item, UserProfile)
        and trash_item.user_type == UserProfile.UserType.IDENTITY
    ):
        _clear_authorized_subject("auth.User", trash_item.user_id)
