from django.dispatch import Signal

automation_workflow_created = Signal()
automation_workflow_deleted = Signal()
automation_workflow_updated = Signal()
automation_workflow_published = Signal()
automation_workflows_reordered = Signal()
