from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from baserow.core.cache import invalidate_cached_settings
from baserow.core.models import Settings, UserProfile
from baserow.core.user.cache import invalidate_cached_user


@receiver(post_save, sender=settings.AUTH_USER_MODEL, dispatch_uid="cache_user_save")
def invalidate_user_cache_on_user_save(sender, instance, **kwargs):
    transaction.on_commit(lambda: invalidate_cached_user(instance.id))


@receiver(post_save, sender=UserProfile, dispatch_uid="cache_profile_save")
def invalidate_user_cache_on_profile_save(sender, instance, **kwargs):
    transaction.on_commit(lambda: invalidate_cached_user(instance.user_id))


@receiver(
    post_delete, sender=settings.AUTH_USER_MODEL, dispatch_uid="cache_user_delete"
)
def invalidate_user_cache_on_user_delete(sender, instance, **kwargs):
    transaction.on_commit(lambda: invalidate_cached_user(instance.id))


@receiver(post_delete, sender=UserProfile, dispatch_uid="cache_profile_delete")
def invalidate_user_cache_on_profile_delete(sender, instance, **kwargs):
    transaction.on_commit(lambda: invalidate_cached_user(instance.user_id))


@receiver(post_save, sender=Settings, dispatch_uid="cache_settings_save")
def invalidate_settings_cache_on_save(sender, **kwargs):
    transaction.on_commit(invalidate_cached_settings)
