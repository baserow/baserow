"""
Limits on how many items one tool call may ask for. A call over a limit is refused
before anything is saved.

They bound the item count, not the database work: each created or moved element
still reloads its page, so a call's cost also grows with the size of the page.
"""

# Pages, elements, data sources, actions or moves in one call, and in each phase of
# setup_page.
MAX_ITEMS_PER_CALL = 50

# Items inside one of those, like menu items, table columns or field mappings.
MAX_NESTED_ITEMS = 100
