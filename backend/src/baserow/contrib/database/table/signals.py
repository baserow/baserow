from django.db.models.signals import post_delete
from django.dispatch import Signal, receiver

from baserow.contrib.database.table.cache import invalidate_table_in_model_cache
from baserow.contrib.database.table.models import Table

table_created = Signal()
table_updated = Signal()
table_deleted = Signal()
tables_reordered = Signal()
table_schema_changed = Signal()
table_usage_updated = Signal()


@receiver(post_delete, sender=Table)
def invalidate_model_cache_when_table_deleted(sender, instance, **kwargs):
    invalidate_table_in_model_cache(instance.id)
