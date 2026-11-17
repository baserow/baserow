import time
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test.utils import override_settings

import pytest

REDIS_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "baserow.ws.channel_layer.RetryingRedisChannelLayer",
        "CONFIG": {"hosts": [{"address": "redis://redis:6379/0"}]},
    }
}
COMMAND = "baserow.ws.management.commands.cleanup_dead_channel_subscriptions"


@pytest.fixture
def channel_layer_redis(channel_layer_redis):
    with (
        override_settings(CHANNEL_LAYERS=REDIS_CHANNEL_LAYERS),
        patch(f"{COMMAND}.SECOND_LOOK_AFTER_SECONDS", 0),
    ):
        yield channel_layer_redis


def fill(client):
    now = time.time()
    client.zadd(
        "asgi:group:users",
        {
            "specific.dead!a": now,
            "specific.dead!b": now,
            "specific.alive!c": now,
            "specific.busy!d": now,
            "specific.idle!e": now,
            "sse_client_f": now,
        },
    )
    client.zadd(
        "asgi:group:table-1",
        {
            "specific.dead!a": now,
            "specific.alive!c": now - 3600,
            "specific.alive!g": now - 2 * 86400,
            "specific.long_gone!h": now - 3 * 86400,
            "sse_client_i": now - 3 * 86400,
        },
    )
    client.zadd("asgispecific.dead!", {f"m{i}": now - 15 for i in range(100)})
    client.zadd("asgispecific.dead!$inflight", {"m": now - 300})
    client.zadd("asgispecific.busy!", {f"m{i}": now - 3 for i in range(100)})
    client.zadd("asgispecific.alive!", {"m": now - 0.2})


def members(client, group):
    return sorted(member.decode() for member in client.zrange(group, 0, -1))


def test_cleanup_removes_dead_and_expired_memberships(channel_layer_redis):
    fill(channel_layer_redis)
    out = StringIO()

    call_command("cleanup_dead_channel_subscriptions", stdout=out)

    assert members(channel_layer_redis, "asgi:group:users") == [
        "specific.alive!c",
        "specific.busy!d",
        "specific.idle!e",
        "sse_client_f",
    ]
    assert members(channel_layer_redis, "asgi:group:table-1") == ["specific.alive!c"]
    assert not channel_layer_redis.exists("asgispecific.dead!")
    assert not channel_layer_redis.exists("asgispecific.dead!$inflight")
    assert channel_layer_redis.exists("asgispecific.busy!")
    assert "specific.dead! is dead: 3 memberships" in out.getvalue()
    assert "1 of 4 processes are dead, with 3 memberships" in out.getvalue()
    assert "Removed 6 memberships." in out.getvalue()


def test_cleanup_dry_run_removes_nothing(channel_layer_redis):
    fill(channel_layer_redis)
    out = StringIO()

    call_command("cleanup_dead_channel_subscriptions", "--dry-run", stdout=out)

    assert len(members(channel_layer_redis, "asgi:group:users")) == 6
    assert len(members(channel_layer_redis, "asgi:group:table-1")) == 5
    assert channel_layer_redis.exists("asgispecific.dead!")
    assert "specific.dead! is dead: 3 memberships" in out.getvalue()
    assert "3 memberships in 1 groups are older" in out.getvalue()
    assert "Removed" not in out.getvalue()


def test_cleanup_keeps_a_process_that_reads_its_mailbox_again(channel_layer_redis):
    fill(channel_layer_redis)
    out = StringIO()

    async def read_the_mailbox(seconds):
        channel_layer_redis.zpopmin("asgispecific.dead!", 5)

    with patch(f"{COMMAND}.asyncio.sleep", read_the_mailbox):
        call_command("cleanup_dead_channel_subscriptions", stdout=out)

    assert len(members(channel_layer_redis, "asgi:group:users")) == 6
    assert channel_layer_redis.exists("asgispecific.dead!")
    assert "0 of 4 processes are dead" in out.getvalue()


def test_cleanup_removes_a_process_whose_messages_expired(channel_layer_redis):
    now = time.time()
    channel_layer_redis.zadd("asgi:group:users", {"specific.dead!a": now})
    channel_layer_redis.zadd("asgispecific.dead!", {"m": now - 61})

    async def expire_the_message(seconds):
        channel_layer_redis.delete("asgispecific.dead!")

    with patch(f"{COMMAND}.asyncio.sleep", expire_the_message):
        call_command("cleanup_dead_channel_subscriptions", stdout=StringIO())

    assert members(channel_layer_redis, "asgi:group:users") == []


def test_cleanup_keeps_a_process_that_is_behind_without_a_full_mailbox(
    channel_layer_redis,
):
    now = time.time()
    channel_layer_redis.zadd("asgi:group:users", {"specific.slow!a": now})
    channel_layer_redis.zadd(
        "asgispecific.slow!", {f"m{i}": now - 15 for i in range(5)}
    )

    call_command("cleanup_dead_channel_subscriptions", stdout=StringIO())

    assert members(channel_layer_redis, "asgi:group:users") == ["specific.slow!a"]
    assert channel_layer_redis.exists("asgispecific.slow!")


def test_cleanup_needs_the_redis_channel_layer():
    with pytest.raises(CommandError, match="Redis channel layer"):
        call_command("cleanup_dead_channel_subscriptions")
