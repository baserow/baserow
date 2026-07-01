"""Shared constants for the database views layer."""

# Default number of group-by groups per page. Lives in the views layer so the handler
# and the API serializers can share it without the handler importing from the API layer.
GROUP_BY_DATA_DEFAULT_LIMIT = 40
