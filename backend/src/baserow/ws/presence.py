import json
import uuid
from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable

from loguru import logger

from baserow.core.async_redis import get_async_redis
from baserow.ws.registries import page_registry
from baserow.ws.types import (
    ActivePresenceEntry,
    PresenceMembershipMessage,
)

if TYPE_CHECKING:
    from baserow.ws.consumers import CoreConsumer

PRESENCE_KEY_PREFIX = "presence:"
PRESENCE_SPACE_TTL = 43200  # 12 hours


def _is_valid_entry(data) -> bool:
    return isinstance(data, dict) and isinstance(data.get("user_id"), int)


def make_page_key(page_type: str, parameters: dict) -> str:
    """
    Build a deterministic key for a page subscription (type + sorted params).

    :param page_type: The registered page type name.
    :param parameters: The page subscription parameters.
    :return: A stable string key for this page subscription.
    """

    sorted_params = sorted(parameters.items())
    return f"{page_type}:{','.join(f'{k}={v}' for k, v in sorted_params)}"


@runtime_checkable
class PresenceHandlerProtocol(Protocol):
    """Per-connection presence lifecycle: page subscribe/unsubscribe and cleanup."""

    async def handle_page_subscribed(
        self, page_type_name: str, parameters: dict
    ) -> None: ...

    async def handle_page_unsubscribed(
        self, page_type_name: str, parameters: dict
    ) -> None: ...

    async def leave_all_spaces(self) -> None: ...


class NullPresenceHandler:
    """No-op handler used when no authenticated user is present."""

    async def handle_page_subscribed(
        self, page_type_name: str, parameters: dict
    ) -> None:
        pass

    async def handle_page_unsubscribed(
        self, page_type_name: str, parameters: dict
    ) -> None:
        pass

    async def leave_all_spaces(self) -> None:
        pass


class PresenceSpace:
    """
    Identity and Redis storage for a single presence space.

    Takes a ``name`` (e.g. ``"table-42"``); Redis key and channel group
    name are derived deterministically.
    """

    def __init__(self, name: str):
        self.name = name

    @property
    def redis_key(self) -> str:
        return f"{PRESENCE_KEY_PREFIX}{self.name}"

    @property
    def channel_group(self) -> str:
        return f"presence.{self.name}"

    async def _fetch_and_clean_entries(self) -> dict[str, dict]:
        """
        Read all entries from Redis, remove corrupt/invalid ones, return valid.
        """

        redis = await get_async_redis()
        raw = await redis.hgetall(self.redis_key)
        entries: dict[str, dict] = {}
        corrupt: list[str] = []
        for pid, value in raw.items():
            try:
                data = json.loads(value)
            except (ValueError, TypeError):
                corrupt.append(pid)
                continue
            if _is_valid_entry(data):
                entries[pid] = data
            else:
                corrupt.append(pid)
        if corrupt:
            await redis.hdel(self.redis_key, *corrupt)
        return entries

    async def join(self, presence_id: str, user_id: int) -> None:
        """
        Add a presence entry to this space in Redis.

        :param presence_id: Unique identifier for this connection's presence.
        :param user_id: The user who owns this connection.
        """

        redis = await get_async_redis()
        entry = json.dumps({"user_id": user_id})
        await redis.hset(self.redis_key, presence_id, entry)
        await redis.expire(self.redis_key, PRESENCE_SPACE_TTL)

    async def remove_entry(self, presence_id: str) -> None:
        """
        Remove a single presence entry from this space in Redis.

        :param presence_id: The presence entry to remove.
        """

        redis = await get_async_redis()
        await redis.hdel(self.redis_key, presence_id)
        await redis.expire(self.redis_key, PRESENCE_SPACE_TTL)

    async def get_members(
        self, exclude_presence_id: Optional[str] = None
    ) -> list[ActivePresenceEntry]:
        """
        Return all members, optionally excluding presence_id.

        :param exclude_presence_id: If set, omit this entry from the result
            (used to exclude self from members response).
        :return: List of presence members.
        """

        entries = await self._fetch_and_clean_entries()
        return [
            ActivePresenceEntry(
                user_id=data["user_id"],
                presence_id=pid,
            )
            for pid, data in entries.items()
            if pid != exclude_presence_id
        ]


class PresenceHandler:
    """Per-connection presence handler owning the full join/leave lifecycle."""

    def __init__(
        self,
        consumer: "CoreConsumer",
        web_socket_id: str,
        user_id: int,
    ):
        self._consumer = consumer
        self._web_socket_id = web_socket_id
        self.user_id = user_id
        self.presence_id = str(uuid.uuid4())
        self._space_pages: dict[str, set[str]] = {}
        self._page_to_space: dict[str, str] = {}

    # -- Page lifecycle (called by consumer) --

    async def handle_page_subscribed(
        self, page_type_name: str, parameters: dict
    ) -> None:
        """
        Join the presence space for this page, send current members to the
        subscriber, and broadcast join to other members.

        :param page_type_name: The registered page type name.
        :param parameters: The page subscription parameters.
        """

        try:
            space_name = self.resolve_space_name(page_type_name, parameters)
            if space_name is None:
                return

            page_key = make_page_key(page_type_name, parameters)
            if page_key in self._page_to_space:
                return

            already_in_space = space_name in self._space_pages

            if already_in_space:
                self._page_subscribed(page_key, space_name)
                return

            space = PresenceSpace(name=space_name)
            await self._consumer.channel_layer.group_add(
                space.channel_group, self._consumer.channel_name
            )
            members = await self._join(space)
            self._page_subscribed(page_key, space_name)
            await self._consumer.send_json(
                {
                    "type": "presence.members",
                    "space": space_name,
                    "entries": members,
                }
            )
            await self._broadcast_join(space)
        except Exception:
            logger.exception("Presence subscribe failed for page {}", page_type_name)

    async def handle_page_unsubscribed(
        self, page_type_name: str, parameters: dict
    ) -> None:
        """
        Leave the presence space if this was the last page mapping to it.

        :param page_type_name: The registered page type name.
        :param parameters: The page subscription parameters.
        """

        page_key = make_page_key(page_type_name, parameters)
        space_name = self._page_to_space.get(page_key)
        if space_name is None:
            return

        remaining = self._space_pages.get(space_name, set()) - {page_key}

        if remaining:
            self._page_unsubscribed(page_key)
            return

        try:
            space = PresenceSpace(name=space_name)
            await self._leave(space)
            await self._broadcast_leave(space)
            await self._consumer.send_json(
                {
                    "type": "presence.space_discard",
                    "space": space_name,
                }
            )
            await self._consumer.channel_layer.group_discard(
                space.channel_group, self._consumer.channel_name
            )
            self._page_unsubscribed(page_key)
        except Exception:
            logger.exception("Presence unsubscribe failed for space {}", space_name)

    async def leave_all_spaces(self) -> None:
        """
        Leave every presence space this connection is in. Called during
        disconnect to broadcast leave and clean up Redis entries.
        """

        for space_name in list(self._space_pages.keys()):
            try:
                space = PresenceSpace(name=space_name)
                await self._leave(space)
                await self._broadcast_leave(space)
                await self._consumer.channel_layer.group_discard(
                    space.channel_group, self._consumer.channel_name
                )
            except Exception:
                logger.exception("Presence cleanup failed for space {}", space_name)
        self._space_pages.clear()
        self._page_to_space.clear()

    # -- Page-to-space tracking (internal) --

    def _page_subscribed(self, page_key: str, space_name: str) -> None:
        """
        Record a page→space mapping. Called after external side effects succeed.
        """

        self._page_to_space[page_key] = space_name
        self._space_pages.setdefault(space_name, set()).add(page_key)

    def _page_unsubscribed(self, page_key: str) -> None:
        """
        Remove a page→space mapping. Called after external side effects succeed.
        """

        space_name = self._page_to_space.pop(page_key, None)
        if space_name is None:
            return
        page_keys = self._space_pages.get(space_name)
        if page_keys is not None:
            page_keys.discard(page_key)
            if not page_keys:
                del self._space_pages[space_name]

    # -- Space operations (Redis via PresenceSpace) --

    async def _join(self, space: PresenceSpace) -> list[ActivePresenceEntry]:
        await space.join(self.presence_id, self.user_id)
        return await space.get_members(exclude_presence_id=self.presence_id)

    async def _leave(self, space: PresenceSpace) -> None:
        await space.remove_entry(self.presence_id)

    # -- Broadcast (ephemeral — no record_realtime_event) --

    async def _broadcast(self, space: PresenceSpace, payload: dict) -> None:
        await self._consumer.channel_layer.group_send(
            space.channel_group,
            {
                "type": "broadcast_to_group",
                "payload": payload,
                "ignore_web_socket_id": self._web_socket_id,
            },
        )

    async def _broadcast_join(self, space: PresenceSpace) -> None:
        payload: PresenceMembershipMessage = {
            "type": "presence.join",
            "space": space.name,
            "user_id": self.user_id,
            "presence_id": self.presence_id,
        }
        await self._broadcast(space, payload)

    async def _broadcast_leave(self, space: PresenceSpace) -> None:
        payload: PresenceMembershipMessage = {
            "type": "presence.leave",
            "space": space.name,
            "user_id": self.user_id,
            "presence_id": self.presence_id,
        }
        await self._broadcast(space, payload)

    # -- Helpers --

    @staticmethod
    def resolve_space_name(page_type_name: str, parameters: dict) -> Optional[str]:
        """
        Look up the presence space name for a page type via the registry.

        :param page_type_name: The registered page type name.
        :param parameters: The page subscription parameters.
        :return: The space name, or None if the page type does not exist or
            does not participate in presence.
        """

        try:
            page_type = page_registry.get(page_type_name)
        except page_registry.does_not_exist_exception_class:
            return None
        return page_type.get_presence_space_name(**parameters)
