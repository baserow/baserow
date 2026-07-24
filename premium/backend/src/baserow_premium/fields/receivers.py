from django.dispatch import receiver

from baserow.contrib.database.table.signals import table_schema_changed
from baserow.core.cache import local_cache


@receiver(table_schema_changed)
def invalidate_ai_prompt_field_ids_cache(sender, table_id, **kwargs):
    # Invalidate the cached field ids used by AI prompt validation (see
    # visitors.get_table_field_ids) when a field is added/updated/trashed/restored.
    local_cache.delete(f"ai_prompt_table_field_ids_{table_id}")
