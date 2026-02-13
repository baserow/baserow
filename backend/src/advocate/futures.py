from concurrent.futures import ThreadPoolExecutor

import requests_futures.sessions
from requests.adapters import DEFAULT_POOLSIZE

from . import Session


class FuturesSession(requests_futures.sessions.FuturesSession, Session):
    def __init__(self, executor=None, max_workers=2, session=None, *args, **kwargs):
        adapter_kwargs = {}
        if executor is None:
            executor = ThreadPoolExecutor(max_workers=max_workers)
            # set connection pool size equal to max_workers if needed
            if max_workers > DEFAULT_POOLSIZE:
                adapter_kwargs = dict(
                    pool_connections=max_workers, pool_maxsize=max_workers
                )
        kwargs["_adapter_kwargs"] = adapter_kwargs
        Session.__init__(self, *args, **kwargs)
        self.executor = executor
        self.session = session

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
