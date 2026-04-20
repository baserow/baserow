from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from baserow_premium.license.cache import invalidate_cached_instance_wide_licenses
from baserow_premium.license.models import License


@receiver(post_save, sender=License, dispatch_uid="cache_license_save")
def invalidate_license_cache_on_save(sender, **kwargs):
    transaction.on_commit(invalidate_cached_instance_wide_licenses)


@receiver(post_delete, sender=License, dispatch_uid="cache_license_delete")
def invalidate_license_cache_on_delete(sender, **kwargs):
    transaction.on_commit(invalidate_cached_instance_wide_licenses)
