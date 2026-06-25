import os

import pytest
from fakeredis.aioredis import FakeRedis
from loguru import logger

from baserow.config.settings.test import _fake_redis_server
from baserow.core.async_redis import set_async_redis

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@pytest.fixture
def caplog_loguru(caplog):
    handler_id = logger.add(caplog.handler, format="{message}")
    yield caplog
    logger.remove(handler_id)


@pytest.fixture(autouse=True)
def _inject_fake_async_redis():
    """
    Inject a FakeRedis async client sharing the same FakeServer as
    django-redis (sync) so both sync assertions and async production
    code hit the same in-memory store.
    """

    client = FakeRedis(server=_fake_redis_server, decode_responses=True)
    set_async_redis(client)
    yield
    set_async_redis(None)
