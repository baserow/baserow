from django.dispatch import Signal

from loguru import logger


class ObservingSignal(Signal):
    """
    A signal whose receivers only observe a click, sent with `send_robust` so
    one that fails is logged rather than failing the click.

    Only the class of the failure is logged. Django's own log line carries
    the message and a traceback, whose frames can hold what a click sent, so
    `_log_robust_failure` is overridden rather than left to Django's default.
    """

    def _log_robust_failure(self, receiver, err):
        logger.error(
            "Receiver {receiver} of a button field signal failed with {exception}.",
            receiver=getattr(receiver, "__qualname__", repr(receiver)),
            exception=type(err).__name__,
        )


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

# Sent once per server-side action with `field`, `succeeded`, `position` and
# `duration_ms`, and with `result` when it succeeded. Receivers must not read
# the result's data, which for an external action can name the address, and must
# not write to `result` or `dispatch_context`, which later actions read. A
# receiver handles its own failures: the action already ran, so one that raises
# is logged and does not fail the click, but a callable object that raises also
# stops the receivers behind it.
workflow_action_dispatched = Signal()

# Sent with the button fields of one table whose `has_workflow_actions` or
# `requires_reconfiguration` may have changed, so every page showing them can
# send them out. Kept apart from `field_updated`, which makes the client
# refetch the whole grid.
button_fields_updated = Signal()

# Once per click that reached the dispatch view with an existing button field,
# refused clicks included, with what became of it.
button_field_dispatched = ObservingSignal()
