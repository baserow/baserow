"""
Limits on how much one tool call may ask for, so its database work stays bounded.
A call over a limit is refused before anything is saved.
"""

# Pages, elements, data sources, actions or moves in one call, and in each phase of
# setup_page.
MAX_ITEMS_PER_CALL = 50

# Items inside one of those, like menu items, table columns or field mappings.
MAX_NESTED_ITEMS = 100
