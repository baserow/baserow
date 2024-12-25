import asyncio

from loguru import logger


class dummy_context:
    async def __aenter__(self):
        pass

    async def __aexit__(self, exc_type, exc, traceback):
        pass


class ConcurrencyLimiterASGI:
    """
    Helper wrapper on ASGI app to limit the number of requests handled
    at the same time.
    """

    def __init__(self, app, max_concurrency: int | None = None):
        self.app = app
        logger.info(f"Setting ASGI app concurrency to {max_concurrency}")
        self.semaphore = (
            asyncio.Semaphore(max_concurrency)
            if (isinstance(max_concurrency, int) and max_concurrency > 0)
            else dummy_context()
        )

    async def __call__(self, scope, receive, send):
        async with self.semaphore:
            await self.app(scope, receive, send)
