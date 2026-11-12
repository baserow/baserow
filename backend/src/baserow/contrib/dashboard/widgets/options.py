"""Collect context references needed by dashboard option formulas."""

from baserow.contrib.dashboard.data_providers import (
    dashboard_options_data_provider_registry,
)


def get_option_context_fields(widgets):
    """Supply dropdown formulas to the context provider for reference extraction."""
    return dashboard_options_data_provider_registry.get(
        "data_source_context"
    ).get_referenced_fields(
        widget.options
        for widget in widgets
        if widget.get_type().type == "text_filter" and widget.mode == "dropdown"
    )
