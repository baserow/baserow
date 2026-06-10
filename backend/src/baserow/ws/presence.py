import json
import uuid
from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable

from channels.db import database_sync_to_async
from django_redis import get_redis_connection
from loguru import logger

from baserow.ws.registries import page_registry
from baserow.ws.types import (
    ActivePresenceEntry,
    PresenceMembershipMessage,
)

if TYPE_CHECKING:
    from baserow.ws.consumers import CoreConsumer

PRESENCE_KEY_PREFIX = "presence:"


def _get_redis():
    return get_redis_connection("default")


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

    def _sync_read_all_entries(self) -> tuple[dict[str, dict], list[str]]:
        redis = _get_redis()
        raw = redis.hgetall(self.redis_key)
        entries: dict[str, dict] = {}
        corrupt: list[str] = []
        for raw_key, value in raw.items():
            pid = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
            val = value.decode() if isinstance(value, bytes) else value
            try:
                entries[pid] = json.loads(val)
            except (ValueError, TypeError):
                corrupt.append(pid)
        return entries, corrupt

    async def _fetch_and_clean_entries(self) -> dict[str, dict]:
        """
        Read all entries from Redis, remove corrupt ones, return valid.
        """

        entries, corrupt = await database_sync_to_async(self._sync_read_all_entries)()
        if corrupt:
            await database_sync_to_async(self._sync_hdel)(*corrupt)
        return entries

    def _sync_hdel(self, *fields: str) -> None:
        redis = _get_redis()
        redis.hdel(self.redis_key, *fields)

    def _sync_add_entry(self, presence_id: str, user_id: int) -> None:
        redis = _get_redis()
        entry = json.dumps({"user_id": user_id})
        redis.hset(self.redis_key, presence_id, entry)

    async def join(self, presence_id: str, user_id: int) -> None:
        """
        Add a presence entry to this space in Redis.

        :param presence_id: Unique identifier for this connection's presence.
        :param user_id: The user who owns this connection.
        """

        await database_sync_to_async(self._sync_add_entry)(presence_id, user_id)

    async def remove_entry(self, presence_id: str) -> None:
        """
        Remove a single presence entry from this space in Redis.

        :param presence_id: The presence entry to remove.
        """

        await database_sync_to_async(self._sync_hdel)(presence_id)

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
                user_id=data.get("user_id"),
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
            space_name = await self.resolve_space_name(page_type_name, parameters)
            if space_name is None:
                return

            page_key = make_page_key(page_type_name, parameters)
            is_new_space = self._page_subscribed(page_key, space_name)
            if not is_new_space:
                return

            space = PresenceSpace(name=space_name)
            await self._consumer.channel_layer.group_add(
                space.channel_group, self._consumer.channel_name
            )
            members = await self._join(space)
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
        left_space_name = self._page_unsubscribed(page_key)
        if not left_space_name:
            return

        try:
            space = PresenceSpace(name=left_space_name)
            await self._leave(space)
            await self._broadcast_leave(space)
            await self._consumer.send_json(
                {
                    "type": "presence.space_discard",
                    "space": left_space_name,
                }
            )
            await self._consumer.channel_layer.group_discard(
                space.channel_group, self._consumer.channel_name
            )
        except Exception:
            self._page_to_space[page_key] = left_space_name
            self._space_pages.setdefault(left_space_name, set()).add(page_key)
            logger.exception(
                "Presence unsubscribe failed for space {}", left_space_name
            )

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

    def _page_subscribed(self, page_key: str, space_name: str) -> bool:
        """
        Track a page→space mapping.

        :param page_key: Deterministic key for the page subscription.
        :param space_name: The presence space this page maps to.
        :return: True if this is the first page for this space (new join).
        """

        self._page_to_space[page_key] = space_name
        if space_name not in self._space_pages:
            self._space_pages[space_name] = {page_key}
            return True
        self._space_pages[space_name].add(page_key)
        return False

    def _page_unsubscribed(self, page_key: str) -> Optional[str]:
        """
        Remove a page→space mapping.

        :param page_key: Deterministic key for the page subscription.
        :return: The space name if this was the last page referencing it,
            otherwise None.
        """

        space_name = self._page_to_space.pop(page_key, None)
        if space_name is None:
            return None
        page_keys = self._space_pages.get(space_name)
        if page_keys is not None:
            page_keys.discard(page_key)
            if not page_keys:
                del self._space_pages[space_name]
                return space_name
        return None

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
    async def resolve_space_name(
        page_type_name: str, parameters: dict
    ) -> Optional[str]:
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
        return await database_sync_to_async(page_type.get_presence_space_name)(
            **parameters
        )
