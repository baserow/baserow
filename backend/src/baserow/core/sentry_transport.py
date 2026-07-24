import json

from loguru import logger
from sentry_sdk.transport import Transport

from baserow.core.sentry import SENTRY_LOG_PREFIX, log_sentry_event_to_console


class ConsoleSentryTransport(Transport):
    """
    A transport that logs Sentry events locally instead of sending them to Sentry.
    """

    def capture_event(self, event):
        log_sentry_event_to_console(event)

    def capture_envelope(self, envelope):
        for item in envelope.items:
            item_type = item.headers.get("type", "unknown")
            payload = item.get_bytes().decode("utf-8", errors="replace")

            if item_type == "event":
                try:
                    log_sentry_event_to_console(json.loads(payload))
                    continue
                except json.JSONDecodeError:
                    pass

            logger.error(
                f"{SENTRY_LOG_PREFIX} [ENVELOPE] [{item_type.upper()}] {payload}"
            )
