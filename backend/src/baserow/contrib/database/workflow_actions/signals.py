from django.dispatch import Signal

workflow_action_created = Signal()
workflow_action_updated = Signal()
workflow_action_deleted = Signal()
workflow_actions_reordered = Signal()

# Sent once per click before the lock is taken, with the server-side actions
# the click is about to run, as a tuple a receiver cannot filter. Not sent for
# a button with only frontend-only actions. A receiver may raise to refuse the
# click; nothing has happened yet.
button_field_before_dispatch = Signal()

# Sent once per server-side action, on success with `result` and on failure
# with `exception`, in both cases with `duration_ms` and the dispatched
# `field`. Receivers must not read the result's data or the exception's text,
# which for an external action name the address, and must not write to
# `result` or `dispatch_context`, which later actions read. The action already
# ran, so a receiver that fails is logged and does not fail the click.
workflow_action_dispatched = Signal()
