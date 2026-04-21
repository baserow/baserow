from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver

from .models import Asset, AssetVersion


@receiver(pre_delete, sender=Asset)
def delete_asset_files(sender, instance, **kwargs):
    """Delete asset files from storage when asset is deleted."""
    if instance.file:
        instance.file.delete(save=False)


@receiver(pre_delete, sender=AssetVersion)
def delete_version_files(sender, instance, **kwargs):
    """Delete version files from storage when version is deleted."""
    if instance.file:
        instance.file.delete(save=False)
