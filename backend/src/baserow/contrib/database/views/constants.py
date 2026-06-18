"""Shared constants for the database views layer."""

# Default number of group-by groups returned per page. Defined in the views layer
# so the handler and the API serializers can share it without the handler having
# to import from the API layer.
GROUP_BY_DATA_DEFAULT_LIMIT = 40
