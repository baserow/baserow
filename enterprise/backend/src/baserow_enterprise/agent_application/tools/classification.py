"""
Read/write classification of the workspace tools an agent can call. This
powers both the "read only" mode of the Baserow workspace tools and the
approval queue, which only intercepts tools that change something.
"""

# Tools that only read workspace data. Everything else is treated as a
# write, so a newly added assistant tool fails closed (requires approval and
# is unavailable in read-only mode) until it is explicitly classified here.
READ_ASSISTANT_TOOLS = {
    # core
    "list_builders",
    # database
    "list_tables",
    "get_tables_schema",
    "list_rows",
    "list_views",
    "generate_formula",
    # automation
    "list_workflows",
    "list_nodes",
    # builder
    "list_pages",
    "list_data_sources",
    "list_elements",
    "list_actions",
    # docs
    "search_user_docs",
}

READ_TOOL_PREFIXES = ("list_", "get_", "search_")

# Write-classified tools that don't change anything by themselves and
# therefore skip the approval queue: `load_row_tools` only unlocks the
# per-table row tools, and those row writes are approval-gated themselves.
APPROVAL_EXEMPT_TOOLS = {"load_row_tools"}


def is_write_tool(tool_name: str) -> bool:
    """
    Whether the given workspace tool changes data. Note that
    `load_row_tools` counts as a write because it only unlocks the per-table
    row write tools, so it is hidden entirely in read-only mode.
    """

    return tool_name not in READ_ASSISTANT_TOOLS and not tool_name.startswith(
        READ_TOOL_PREFIXES
    )
