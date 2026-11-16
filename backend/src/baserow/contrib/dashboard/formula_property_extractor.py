"""Collect service properties used by dashboard widgets."""

from baserow.core.cache import global_cache
from baserow.core.utils import merge_dicts_no_duplicates

WIDGET_PROPERTIES_CACHE_TTL_SECONDS = 60 * 60
WIDGET_PROPERTIES_LOCK_TIMEOUT_SECONDS = 60


def get_dashboard_used_property_names(widgets):
    """Ask each widget type for the service properties used by its formulas."""
    result = {}
    for widget in widgets:
        result = merge_dicts_no_duplicates(
            result,
            global_cache.get(
                get_widget_properties_cache_key(widget.id),
                default=lambda: widget.get_type().extract_properties(widget),
                timeout=WIDGET_PROPERTIES_CACHE_TTL_SECONDS,
                lock_timeout=WIDGET_PROPERTIES_LOCK_TIMEOUT_SECONDS,
            ),
        )
    return result


def get_widget_properties_cache_key(widget_id):
    return f"dashboard_widget_used_properties_{widget_id}"


def invalidate_widget_properties(widget_id):
    global_cache.invalidate(get_widget_properties_cache_key(widget_id))
