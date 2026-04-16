from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from baserow.core.models import UserProfile


@receiver(
    post_save, sender=settings.AUTH_USER_MODEL, dispatch_uid="jwt_cache_user_save"
)
def invalidate_user_cache_on_user_save(sender, instance, **kwargs):
    from baserow.core.user.cache import invalidate_cached_user

    invalidate_cached_user(instance.id)


@receiver(post_save, sender=UserProfile, dispatch_uid="jwt_cache_profile_save")
def invalidate_user_cache_on_profile_save(sender, instance, **kwargs):
    from baserow.core.user.cache import invalidate_cached_user

    invalidate_cached_user(instance.user_id)


@receiver(
    post_delete, sender=settings.AUTH_USER_MODEL, dispatch_uid="jwt_cache_user_delete"
)
def invalidate_user_cache_on_user_delete(sender, instance, **kwargs):
    from baserow.core.user.cache import invalidate_cached_user

    invalidate_cached_user(instance.id)


@receiver(post_delete, sender=UserProfile, dispatch_uid="jwt_cache_profile_delete")
def invalidate_user_cache_on_profile_delete(sender, instance, **kwargs):
    from baserow.core.user.cache import invalidate_cached_user

    invalidate_cached_user(instance.user_id)
