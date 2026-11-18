# The tools that were enabled on develop on 2026-10-19. An endpoint without an
# allow-list (``allowed_tools is None``) may use exactly these tools, so newly added
# tools never reach existing endpoints without an explicit grant.
LEGACY_DEFAULT_TOOLS = [
    "list_databases",
    "list_tables",
    "get_table_schema",
    "list_table_rows",
    "create_rows",
    "update_rows",
    "delete_rows",
]

# Keys pg_advisory_lock(namespace, endpoint id), see
# ``call_with_endpoint_changes_lock``.
ENDPOINT_CHANGES_LOCK_NAMESPACE = 6753

# How long a call keeps trying to take the endpoint's changes lock before it
# asks the client to try again, and how long it waits between tries.
ENDPOINT_CHANGES_LOCK_WAIT_SECONDS = 3
ENDPOINT_CHANGES_LOCK_RETRY_SECONDS = 0.1

LOCKED_MESSAGE = "Something else is changing the same data. Try again in a moment."
