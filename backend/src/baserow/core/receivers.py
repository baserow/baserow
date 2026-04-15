from django.db.models.signals import post_save
from django.dispatch import receiver

from baserow.core.models import UserProfile


@receiver(post_save, sender="auth.User", dispatch_uid="jwt_cache_user_save")
def invalidate_user_cache_on_user_save(sender, instance, **kwargs):
    from baserow.core.user.cache import invalidate_cached_user

    invalidate_cached_user(instance.id)


@receiver(post_save, sender=UserProfile, dispatch_uid="jwt_cache_profile_save")
def invalidate_user_cache_on_profile_save(sender, instance, **kwargs):
    from baserow.core.user.cache import invalidate_cached_user

    invalidate_cached_user(instance.user_id)
