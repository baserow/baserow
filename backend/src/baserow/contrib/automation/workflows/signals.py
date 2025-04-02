from django.dispatch import Signal

workflow_created = Signal()
workflow_deleted = Signal()
workflow_updated = Signal()
workflows_reordered = Signal()
