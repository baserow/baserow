from django.dispatch import Signal

workflow_action_created = Signal()
workflow_action_updated = Signal()
workflow_action_deleted = Signal()
workflow_actions_reordered = Signal()

# Sent with the button fields of one table whose `has_workflow_actions` or
# `requires_reconfiguration` may have changed, so every page showing them can
# send them out. Kept apart from `field_updated`, which makes the client
# refetch the whole grid.
button_fields_updated = Signal()
