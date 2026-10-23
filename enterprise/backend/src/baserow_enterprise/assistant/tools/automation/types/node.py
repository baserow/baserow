"""
The node definitions live in ``baserow.contrib.automation.tools.types``, shared
with MCP.
"""

from baserow.contrib.automation.tools.types import (
    CANONICAL_TO_SHORT_TYPE,
    ROW_TRIGGER_TYPES,
    SUPPORTS_FORMULA,
    ActionNodeCreate,
    AutomationFieldValue,
    NodeUpdate,
    PeriodicTriggerSettings,
    RouterEdgeCreate,
    RouterEdgeUpdate,
    RowsTriggersSettings,
    TriggerNodeCreate,
)

__all__ = [
    "CANONICAL_TO_SHORT_TYPE",
    "ROW_TRIGGER_TYPES",
    "SUPPORTS_FORMULA",
    "ActionNodeCreate",
    "AutomationFieldValue",
    "NodeUpdate",
    "PeriodicTriggerSettings",
    "RouterEdgeCreate",
    "RouterEdgeUpdate",
    "RowsTriggersSettings",
    "TriggerNodeCreate",
]
