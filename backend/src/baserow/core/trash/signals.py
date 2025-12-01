import django.dispatch

before_permanently_deleted = django.dispatch.Signal()
"""
Sent immediately before any trashable item in Baserow is permanently deleted, so that
the trash_item still has a valid id and all CASCADE relations are still intact. This
signal is sent with kwargs containing:

:param trash_item: The actual instance of the trashable item that is about to be
    deleted.
:param trash_item_id : The id of the item that is about to be deleted.
:param parent_id: The parent id of the trashable item if required for that type.
"""

permanently_deleted = django.dispatch.Signal()
"""
Sent when any trashable item in Baserow is permanently deleted with kwargs containing:

:param trash_item: The actual instance of the trashable item that was deleted.
:param trash_item_id : The id of the item that was deleted as trash_item.id will now be
    None.
:param parent_id: The parent id of the trashable item if required for that type.
"""
