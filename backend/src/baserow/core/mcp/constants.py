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
