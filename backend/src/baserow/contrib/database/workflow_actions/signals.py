from django.dispatch import Signal

workflow_action_created = Signal()
workflow_action_updated = Signal()
workflow_action_deleted = Signal()
workflow_actions_reordered = Signal()

# Once per server-side action of a click, whether it succeeded or failed.
# Receivers must not read `exception` messages or `result` data: for an
# external action both can name the address it was pointed at.
workflow_action_dispatched = Signal()
