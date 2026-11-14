"""
Lets Kuma add, update and delete the filters of a Local Baserow service from a
request in the user's words. Applying, validating and saving the changes is done by
``baserow.contrib.integrations.local_baserow.service_filters``, shared with MCP.

The same request runs whether it comes from the chat (the ``update_service_filters``
tool) or from the "Create with Kuma" link in a data source's filter form, so both
entry points behave identically.
"""

from .handler import ServiceFilterRequestResult, run_service_filter_request

__all__ = [
    "ServiceFilterRequestResult",
    "run_service_filter_request",
]
