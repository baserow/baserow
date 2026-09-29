from django.dispatch import Signal

page_created = Signal()
page_loaded = Signal()
page_deleted = Signal()
page_updated = Signal()
pages_reordered = Signal()
