from django.dispatch import receiver

from baserow.contrib.database.table.signals import table_schema_changed
from baserow.core.cache import global_cache, local_cache


@receiver(table_schema_changed)
def invalidate_table_cache(sender, table_id, **kwargs):
    # Invalidate local cache when the table schema is updated
    global_cache.invalidate(invalidate_key=f"table_{table_id}__service_invalidate_key")
    local_cache.delete(f"integration_service_{table_id}_table_model")
