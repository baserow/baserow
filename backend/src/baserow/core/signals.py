from django.dispatch import Signal

from loguru import logger


class ObservingSignal(Signal):
    """
    A signal whose receivers only observe what already happened, sent with
    `send_robust` so one that fails is logged rather than failing the sender.

    Only the class of the failure is logged. Django's own line carries the
    message and a traceback, whose frames can hold what the sender was working
    with, an address a request went to for instance, so `_log_robust_failure`
    is overridden rather than left to Django's default.
    """

    def _log_robust_failure(self, receiver, err):
        logger.error(
            "Receiver {receiver} of {signal} failed with {exception}.",
            receiver=getattr(receiver, "__qualname__", repr(receiver)),
            signal=type(self).__name__,
            exception=type(err).__name__,
        )


before_workspace_user_deleted = Signal()
before_workspace_user_updated = Signal()
before_user_deleted = Signal()

before_workspace_deleted = Signal()

user_updated = Signal()
user_deleted = Signal()
user_restored = Signal()
user_permanently_deleted = Signal()

workspace_created = Signal()
workspace_updated = Signal()
workspace_deleted = Signal()
workspace_restored = Signal()

workspace_user_added = Signal()
workspace_user_updated = Signal()
workspace_user_deleted = Signal()
workspaces_reordered = Signal()

application_created = Signal()
application_updated = Signal()
application_deleted = Signal()
application_imported = Signal()
applications_reordered = Signal()

permissions_updated = Signal()

workspace_invitation_updated_or_created = Signal()
workspace_invitation_accepted = Signal()
workspace_invitation_rejected = Signal()
