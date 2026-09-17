from django.dispatch import Signal

from loguru import logger

workflow_action_created = Signal()
workflow_action_updated = Signal()
workflow_action_deleted = Signal()
workflow_actions_reordered = Signal()

# Once per server-side action of a click, whether it succeeded or failed.
# Receivers must not read `exception` messages or `result` data: for an
# external action both can name the address it was pointed at.
workflow_action_dispatched = Signal()

# Once per click that reached the dispatch view with an existing button field,
# refused clicks included, with what became of it.
button_field_dispatched = Signal()

# Before a click with server-side actions takes its lock, after every
# permission and configuration check. A receiver may raise to refuse the
# click; nothing has run and nothing is held at that point.
button_field_before_dispatch = Signal()


def send_without_failing(signal: Signal, sender, **kwargs) -> None:
    """
    Sends a signal whose receivers only observe, so one that fails is logged
    rather than failing the click it observes.

    Only the class of the failure is logged: loguru prints frame locals beside
    a traceback, and these kwargs can carry an exception naming an address.
    """

    for receiver, response in signal.send_robust(sender, **kwargs):
        if isinstance(response, Exception):
            logger.error(
                "Receiver {receiver} of a button field signal failed with {exception}.",
                receiver=getattr(receiver, "__qualname__", repr(receiver)),
                exception=type(response).__name__,
            )
