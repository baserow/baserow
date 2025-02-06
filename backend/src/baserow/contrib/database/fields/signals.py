from django.db.models.signals import post_delete
from django.dispatch import Signal, receiver

from baserow.contrib.database.fields.models import Field

field_created = Signal()
field_restored = Signal()
field_updated = Signal()
field_deleted = Signal()
before_field_deleted = Signal()
fields_type_changed = Signal()


@receiver(post_delete, sender=Field)
def invalidate_model_cache_when_field_deleted(sender, instance, **kwargs):
    instance.invalidate_table_model_cache()
