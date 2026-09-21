from django.dispatch import Signal

workflow_action_created = Signal()
workflow_action_updated = Signal()
workflow_action_deleted = Signal()
workflow_actions_reordered = Signal()

# Sent once per click, with the lock held and before the audit entry, with the
# server-side actions the click is about to run, as a tuple a receiver cannot
# filter. Not sent for a button with only frontend-only actions, nor for a click
# refused before the lock (permission, deactivated type, misconfigured action,
# already running). A receiver may raise to refuse the click; nothing has run
# yet and the lock is released.
workflow_actions_before_dispatch = Signal()

# Sent once per server-side action with `succeeded`, `position` and
# `duration_ms`, and with `result` when it succeeded. Receivers must not read
# the result's data, which for an external action can name the address, and must
# not write to `result` or `dispatch_context`, which later actions read. A
# receiver handles its own failures: the action already ran, so one that raises
# is logged and does not fail the click, but a callable object that raises also
# stops the receivers behind it.
workflow_action_dispatched = Signal()
