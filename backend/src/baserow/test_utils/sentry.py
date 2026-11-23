from contextlib import contextmanager
from typing import Any, Iterator, Sequence

import sentry_sdk
from sentry_sdk.integrations import Integration
from sentry_sdk.transport import Transport

TEST_SENTRY_DSN = "https://public@example.invalid/1"


class CollectingSentryTransport(Transport):
    """Keeps the events Sentry would send instead of sending them."""

    def __init__(self, options=None):
        super().__init__(options)
        self.events: list[dict[str, Any]] = []

    def capture_envelope(self, envelope):
        self.events.extend(
            item.payload.json for item in envelope.items if item.type == "event"
        )


@contextmanager
def collect_sentry_events(
    integrations: Sequence[Integration] = (),
) -> Iterator[list[dict[str, Any]]]:
    """
    Sends the Sentry events captured inside the block to the returned list instead
    of to Sentry. Set `settings.SENTRY_DSN` too for code that checks it.

    :param integrations: The Sentry integrations to enable, none by default.
    """

    transport = CollectingSentryTransport()
    client = sentry_sdk.Client(
        dsn=TEST_SENTRY_DSN,
        transport=transport,
        default_integrations=False,
        integrations=list(integrations),
    )
    try:
        with sentry_sdk.isolation_scope() as scope:
            scope.set_client(client)
            yield transport.events
    finally:
        client.close()
