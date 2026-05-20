import os
from urllib.parse import urlparse

from django.conf import settings

import pytest
from django_redis import get_redis_connection
from fakeredis import FakeAsyncRedis

from baserow.ws.presence import _set_async_redis

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


def _get_fake_server_and_db():
    """Extract the FakeServer instance and db number from django_redis cache
    config so the async presence pool shares state with sync test assertions."""

    pool_kwargs = settings.CACHES["default"]["OPTIONS"]["CONNECTION_POOL_KWARGS"]
    server = pool_kwargs["server"]
    location = settings.CACHES["default"]["LOCATION"]
    db = int(urlparse(location).path.lstrip("/") or 0)
    return server, db


@pytest.fixture(autouse=True)
def clean_presence_keys():
    redis = get_redis_connection("default")
    fake_server, db = _get_fake_server_and_db()
    async_redis = FakeAsyncRedis(server=fake_server, decode_responses=True, db=db)
    _set_async_redis(async_redis)

    def _flush():
        keys = list(redis.scan_iter(match="presence:*"))
        if keys:
            redis.delete(*keys)

    _flush()
    yield
    _flush()
    _set_async_redis(None)
