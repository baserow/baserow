"""
This file is responsible for caching Table model field attrs. These field attrs are
stored in the generated models cache in a Redis backed Django cache (or in-memory cache
for tests).

We then store cache field_attrs in the cache key:
    `full_table_model_{table_id}_{min_model_version}_{BASEROW_VERSION}`

When we construct a model we:
1. Get the table version using the table.version attribute.
2. Get that tables field_attrs from the cache.
3. Check if the version in the cache matches the latest table version in the db.
4. If they differ, re-query for all the fields and save them in the cache.
5. If they are the same use the cached field attrs.
"""
import typing
import uuid
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.cache import caches
from django.core.exceptions import ImproperlyConfigured

from baserow.core.cache import local_cache
from baserow.version import VERSION as BASEROW_VERSION

if typing.TYPE_CHECKING:
    from baserow.contrib.database.table.models import Table

generated_models_cache = caches[settings.GENERATED_MODEL_CACHE_NAME]


def table_model_cache_entry_key(table_id: int) -> str:
    return f"full_table_model_{table_id}_{BASEROW_VERSION}"


def get_cached_model_field_attrs(table: "Table") -> Optional[Dict[str, Any]]:
    cache_key = table_model_cache_entry_key(table.id)
    cache_entry = generated_models_cache.get(cache_key)

    if cache_entry and cache_entry["version"] == table.version:
        return cache_entry["field_attrs"]
    else:
        return None


def set_cached_model_field_attrs(table: "Table", field_attrs: Dict[str, Any]):
    cache_key = table_model_cache_entry_key(table.id)
    generated_models_cache.set(
        cache_key,
        {"field_attrs": field_attrs, "version": table.version},
        timeout=None,
    )


def clear_generated_model_cache():
    print("Clearing Baserow's internal generated model cache...")
    if hasattr(generated_models_cache, "delete_pattern"):
        generated_models_cache.delete_pattern("full_table_model_*")
    elif settings.TESTS:
        # Just clear the entire cache in tests
        generated_models_cache.clear()
    else:
        raise ImproperlyConfigured(
            "Baserow must be run with a redis cache outside of " "tests."
        )
    print("Done clearing cache.")


def invalidate_table_in_model_cache(table_id: int):
    from baserow.contrib.database.table.models import Table
    from baserow.contrib.database.table.signals import table_schema_changed

    # Send signal for other potential cached values
    table_schema_changed.send(Table, table_id=table_id)

    # Delete model local cache
    local_cache.delete(f"database_table_model_{table_id}*")

    if settings.BASEROW_DISABLE_MODEL_CACHE:
        return None

    new_version = str(uuid.uuid4())
    # Make sure to invalidate ourselves and any directly connected tables.

    Table.objects_and_trash.filter(id=table_id).update(version=new_version)
