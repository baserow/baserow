import asyncio
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from channels_redis.core import RedisChannelLayer
from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from baserow.core.redis import (
    ASYNC_REDIS_PROTOCOL,
    AsyncRetryingConnectionPool,
    async_redis_pool_options,
)
from baserow.ws.channel_layer import RetryingRedisChannelLayer

pytestmark = pytest.mark.asyncio


@asynccontextmanager
async def fake_redis(idle_close=None, read_only_replies=0, hang_up_on=None):
    """
    A minimal RESP2 server that answers +OK, optionally closing idle connections
    like Valkey's `timeout`, rejecting the first writes as read-only like a
    demoted primary, or hanging up after receiving a given command.
    """

    received = []
    state = {"read_only_replies": read_only_replies}

    async def handle(reader, writer):
        try:
            while True:
                try:
                    line = await asyncio.wait_for(reader.readline(), idle_close)
                except asyncio.TimeoutError:
                    return
                if not line:
                    return
                args = []
                for _ in range(int(line[1:])):
                    await reader.readline()
                    args.append((await reader.readline()).strip())
                command = args[0].upper().decode()
                received.append(command)
                if command == hang_up_on:
                    return
                if command == "SET" and state["read_only_replies"]:
                    state["read_only_replies"] -= 1
                    writer.write(b"-READONLY You can't write against a replica.\r\n")
                else:
                    writer.write(b"+OK\r\n")
                await writer.drain()
        finally:
            writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        yield f"redis://127.0.0.1:{port}/0", received
    finally:
        server.close()


def retrying_client(url):
    return Redis.from_pool(
        AsyncRetryingConnectionPool.from_url(url, **async_redis_pool_options())
    )


async def test_pooled_connection_closed_by_server_is_replaced():
    async with fake_redis(idle_close=0.2) as (url, received):
        client = retrying_client(url)
        await client.set("key", "1")
        await asyncio.sleep(0.5)

        assert await client.set("key", "2")
        assert received.count("SET") == 2
        await client.aclose()


async def test_command_rejected_as_read_only_is_retried():
    async with fake_redis(read_only_replies=2) as (url, received):
        client = retrying_client(url)

        with patch("redis.asyncio.retry.sleep"):
            assert await client.set("key", "1")
        assert received.count("SET") == 3
        await client.aclose()


async def test_command_whose_connection_dropped_is_not_retried():
    async with fake_redis(hang_up_on="SET") as (url, received):
        client = retrying_client(url)

        with pytest.raises(RedisConnectionError):
            await client.set("key", "1")
        assert received.count("SET") == 1
        await client.aclose()


async def test_taking_a_connection_from_the_pool_is_retried():
    pool = AsyncRetryingConnectionPool(**async_redis_pool_options())
    connection = object()
    with (
        patch.object(
            ConnectionPool,
            "get_connection",
            side_effect=[RedisConnectionError(), RedisConnectionError(), connection],
        ) as get_connection,
        patch("redis.asyncio.retry.sleep"),
    ):
        assert await pool.get_connection() is connection
    assert get_connection.call_count == 3


async def test_taking_a_connection_from_the_pool_gives_up_after_three_retries():
    pool = AsyncRetryingConnectionPool(**async_redis_pool_options())
    with (
        patch.object(
            ConnectionPool, "get_connection", side_effect=RedisConnectionError()
        ) as get_connection,
        patch("redis.asyncio.retry.sleep"),
    ):
        with pytest.raises(RedisConnectionError):
            await pool.get_connection()
    assert get_connection.call_count == 4


def test_channel_layer_builds_retrying_pools_and_keeps_host_options():
    layer = RetryingRedisChannelLayer(
        hosts=[
            {"address": "redis://redis:6379/0", "socket_timeout": 10},
            {"host": "redis", "port": 6379, "protocol": 3},
        ]
    )

    url_pool = layer.create_pool(0)
    assert isinstance(url_pool, AsyncRetryingConnectionPool)
    assert url_pool.checkout_retry is not None
    assert url_pool.connection_kwargs["protocol"] == ASYNC_REDIS_PROTOCOL
    assert url_pool.connection_kwargs["socket_timeout"] == 10
    assert url_pool.connection_kwargs["host"] == "redis"

    host_pool = layer.create_pool(1)
    assert isinstance(host_pool, AsyncRetryingConnectionPool)
    assert host_pool.connection_kwargs["protocol"] == 3


def test_channel_layer_leaves_sentinel_hosts_to_channels_redis():
    layer = RetryingRedisChannelLayer(
        hosts=[{"master_name": "primary", "sentinels": [("sentinel", 26379)]}]
    )
    with patch.object(RedisChannelLayer, "create_pool") as create_pool:
        assert layer.create_pool(0) is create_pool.return_value
