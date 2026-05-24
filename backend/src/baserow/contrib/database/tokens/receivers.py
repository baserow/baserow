from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from baserow.contrib.database.tokens.cache import invalidate_cached_token
from baserow.contrib.database.tokens.models import Token
from baserow.core.models import UserProfile


@receiver(post_save, sender=Token, dispatch_uid="db_token_cache_save")
def invalidate_db_token_cache_on_save(sender, instance, **kwargs):
    transaction.on_commit(lambda: invalidate_cached_token(instance.key))


@receiver(post_delete, sender=Token, dispatch_uid="db_token_cache_delete")
def invalidate_db_token_cache_on_delete(sender, instance, **kwargs):
    transaction.on_commit(lambda: invalidate_cached_token(instance.key))


def _invalidate_tokens_of_user(user_id: int) -> None:
    keys = Token.objects.filter(user_id=user_id).values_list("key", flat=True)
    for key in keys:
        invalidate_cached_token(key)


@receiver(
    post_save,
    sender=settings.AUTH_USER_MODEL,
    dispatch_uid="db_token_cache_user_save",
)
def invalidate_db_token_cache_on_user_save(sender, instance, **kwargs):
    transaction.on_commit(lambda: _invalidate_tokens_of_user(instance.id))


@receiver(post_save, sender=UserProfile, dispatch_uid="db_token_cache_profile_save")
def invalidate_db_token_cache_on_profile_save(sender, instance, **kwargs):
    transaction.on_commit(lambda: _invalidate_tokens_of_user(instance.user_id))
