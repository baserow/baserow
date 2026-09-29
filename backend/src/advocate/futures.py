import requests_futures.sessions

from . import Session


class FuturesSession(requests_futures.sessions.FuturesSession, Session):
    @property
    def session(self):
        return None

    @session.setter
    def session(self, value):
        if value is not None and not isinstance(value, Session):
            raise NotImplementedError(
                "Setting the .session property to "
                "non-advocate values disabled "
                "to prevent whitelist bypasses"
            )
