import json
import uuid
from typing import TYPE_CHECKING, Any, Optional, Protocol, runtime_checkable

from channels.db import database_sync_to_async
from loguru import logger

from baserow.core.async_redis import get_async_redis
from baserow.ws.registries import (
    InvalidFocusPayloadException,
    page_registry,
    presence_focus_type_registry,
)
from baserow.ws.types import (
    ActivePresenceEntry,
    PresenceMembershipMessage,
)

if TYPE_CHECKING:
    from baserow.ws.consumers import CoreConsumer

ANONYMOUS_USER_ID = -1
PRESENCE_EVENT_PREFIX = "presence."
ANONYMOUS_ALLOWED_PRESENCE_EVENTS = frozenset({"presence.editors_active"})

PRESENCE_KEY_PREFIX = "presence:"
PRESENCE_SPACE_TTL = 43200  # 12 hours


def _is_valid_entry(data: Any) -> bool:
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

    async def handle_focus(self, page_key: str, raw_focus: dict | None) -> None: ...

    async def receive_focus_broadcast(self, event: dict) -> None: ...

    def get_recipient_pages_for_space(
        self, space_name: str
    ) -> list[tuple[str, dict]]: ...

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

    async def handle_focus(self, page_key: str, raw_focus: dict | None) -> None:
        pass

    async def receive_focus_broadcast(self, event: dict) -> None:
        pass

    def get_recipient_pages_for_space(self, space_name: str) -> list[tuple[str, dict]]:
        return []

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

    async def update_entry_focus(
        self, presence_id: str, user_id: int, focus: dict | None
    ) -> None:
        """
        Upsert the presence entry with the given focus in a single pipelined
        round trip. Writing the full entry instead of patching an existing one
        recreates entries whose space hash expired while the connection stayed
        open, so focus keeps working without a resubscribe.

        :param presence_id: The presence entry to upsert.
        :param user_id: The user who owns this connection.
        :param focus: The validated focus dict, or None to clear focus.
        """

        redis = await get_async_redis()
        entry = json.dumps({"user_id": user_id, "focus": focus})
        async with redis.pipeline(transaction=False) as pipe:
            pipe.hset(self.redis_key, presence_id, entry)
            pipe.expire(self.redis_key, PRESENCE_SPACE_TTL)
            await pipe.execute()

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
                focus=data.get("focus"),
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
        self._space_pages: dict[str, dict[str, tuple[str, dict]]] = {}
        self._page_to_space: dict[str, str] = {}

    def get_recipient_pages_for_space(self, space_name: str) -> list[tuple[str, dict]]:
        return list(self._space_pages.get(space_name, {}).values())

    async def handle_page_subscribed(
        self, page_type_name: str, parameters: dict
    ) -> None:
        """
        Join the presence space for this page, send current members to the
        subscriber, and broadcast join to other members.

        :param page_type_name: The registered page type name.
        :param parameters: The page subscription parameters.
        """

        space = None
        already_in_space = False
        try:
            space_name = await self.resolve_space_name(page_type_name, parameters)
            if space_name is None:
                return

            page_key = make_page_key(page_type_name, parameters)
            if page_key in self._page_to_space:
                return

            already_in_space = space_name in self._space_pages
            if already_in_space:
                self._page_subscribed(page_key, space_name, page_type_name, parameters)
                return

            space = PresenceSpace(name=space_name)
            await self._consumer.channel_layer.group_add(
                space.channel_group, self._consumer.channel_name
            )
            members = await self._join(space)
            self._page_subscribed(page_key, space_name, page_type_name, parameters)
            if self.user_id != ANONYMOUS_USER_ID:
                await self._consumer.send_json(
                    {
                        "type": "presence.members",
                        "space": space_name,
                        "entries": self._filter_members_focus(
                            page_type_name, parameters, members
                        ),
                    }
                )
            else:
                if self._has_auth_members(members):
                    await self._send_editors_active(space, active=True)
            await self._broadcast_join(space)
            if self.user_id != ANONYMOUS_USER_ID:
                if not self._has_auth_members(members):
                    await self._signal_editors_active(space, active=True)
        except Exception:
            logger.exception("Presence subscribe failed for page {}", page_type_name)
            # Roll back everything so a later re-subscribe starts clean instead
            # of early-returning on poisoned local state.
            if space is not None and not already_in_space:
                self._page_unsubscribed(page_key)
                try:
                    await space.remove_entry(self.presence_id)
                except Exception:
                    pass
                try:
                    await self._consumer.channel_layer.group_discard(
                        space.channel_group, self._consumer.channel_name
                    )
                except Exception:
                    pass

    async def handle_page_unsubscribed(
        self, page_type_name: str, parameters: dict
    ) -> None:
        """
        Leave the presence space if this was the last page mapping to it.

        Failure domains are split around the Redis removal: if it fails the
        maps stay intact so ``leave_all_spaces`` retries the idempotent
        cleanup at disconnect. Once the Redis entry is gone the maps are
        always committed — keeping them would make a re-subscribe early-return
        on a page key with no Redis entry behind it — so the remaining
        notification side effects are individually best-effort.

        :param page_type_name: The registered page type name.
        :param parameters: The page subscription parameters.
        """

        page_key = make_page_key(page_type_name, parameters)
        space_name = self._page_to_space.get(page_key)
        if space_name is None:
            return

        pages_in_space = self._space_pages.get(space_name, {})
        is_last_page_for_space = len(pages_in_space) == 1 and page_key in pages_in_space
        if not is_last_page_for_space:
            self._page_unsubscribed(page_key)
            return

        space = PresenceSpace(name=space_name)
        try:
            await self._leave(space)
        except Exception:
            logger.exception("Presence unsubscribe failed for space {}", space_name)
            return

        for side_effect in (
            lambda: self._broadcast_leave(space),
            lambda: self._maybe_signal_last_editor_left(space),
            lambda: self._consumer.send_json(
                {
                    "type": "presence.space_discard",
                    "space": space_name,
                }
            ),
            lambda: self._consumer.channel_layer.group_discard(
                space.channel_group, self._consumer.channel_name
            ),
        ):
            try:
                await side_effect()
            except Exception:
                logger.exception(
                    "Presence unsubscribe side effect failed for space {}", space_name
                )

        self._page_unsubscribed(page_key)

    async def handle_focus(self, page_key: str, raw_focus: dict | None) -> None:
        """
        Validate an incoming focus payload, upsert it on this connection's
        presence entry, and broadcast it to the space. The upsert always
        succeeds (recreating an expired entry if needed) and the consumer
        processes its own messages serially, so broadcasting unconditionally
        cannot race this connection's own leave.

        :param page_key: Deterministic key for the page subscription.
        :param raw_focus: The raw focus payload from the client, or None to
            clear focus.
        """

        space_name = self._page_to_space.get(page_key)
        if space_name is None:
            return

        try:
            validated_focus, focus_type_name = (
                presence_focus_type_registry.validate_focus(raw_focus)
            )
        except InvalidFocusPayloadException:
            return

        space = PresenceSpace(name=space_name)
        await space.update_entry_focus(self.presence_id, self.user_id, validated_focus)
        await self._broadcast_focus(space, validated_focus, focus_type_name)

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
                await self._maybe_signal_last_editor_left(space)
                await self._consumer.channel_layer.group_discard(
                    space.channel_group, self._consumer.channel_name
                )
            except Exception:
                logger.exception("Presence cleanup failed for space {}", space_name)
        self._space_pages.clear()
        self._page_to_space.clear()

    def _page_subscribed(
        self,
        page_key: str,
        space_name: str,
        page_type_name: str,
        parameters: dict,
    ) -> None:
        """
        Track a page→space mapping.

        :param page_key: Deterministic key for the page subscription.
        :param space_name: The presence space this page maps to.
        :param page_type_name: The registered page type name.
        :param parameters: The page subscription parameters.
        """

        self._page_to_space[page_key] = space_name
        if space_name not in self._space_pages:
            self._space_pages[space_name] = {page_key: (page_type_name, parameters)}
        else:
            self._space_pages[space_name][page_key] = (page_type_name, parameters)

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
        pages = self._space_pages.get(space_name)
        if pages is not None:
            pages.pop(page_key, None)
            if not pages:
                del self._space_pages[space_name]
                return space_name
        return None

    async def _join(self, space: PresenceSpace) -> list[ActivePresenceEntry]:
        """Add this connection to the space and return existing members."""

        await space.join(self.presence_id, self.user_id)
        return await space.get_members(exclude_presence_id=self.presence_id)

    async def _leave(self, space: PresenceSpace) -> None:
        """Remove this connection's entry from the space."""

        await space.remove_entry(self.presence_id)

    async def _broadcast(self, space: PresenceSpace, payload: dict) -> None:
        """Send a payload to the space's channel group, excluding self."""

        await self._consumer.channel_layer.group_send(
            space.channel_group,
            {
                "type": "broadcast_to_group",
                "payload": payload,
                "ignore_web_socket_id": self._web_socket_id,
            },
        )

    async def _broadcast_join(self, space: PresenceSpace) -> None:
        """Broadcast a join event to other members of the space."""

        payload: PresenceMembershipMessage = {
            "type": "presence.join",
            "space": space.name,
            "user_id": self.user_id,
            "presence_id": self.presence_id,
        }
        await self._broadcast(space, payload)

    async def _broadcast_leave(self, space: PresenceSpace) -> None:
        """Broadcast a leave event to other members of the space."""

        payload: PresenceMembershipMessage = {
            "type": "presence.leave",
            "space": space.name,
            "user_id": self.user_id,
            "presence_id": self.presence_id,
        }
        await self._broadcast(space, payload)

    async def _broadcast_focus(
        self,
        space: PresenceSpace,
        focus: dict | None,
        focus_type_name: str | None,
    ) -> None:
        payload = {
            "type": "presence.focus",
            "space": space.name,
            "user_id": self.user_id,
            "presence_id": self.presence_id,
            "focus": focus,
        }
        await self._consumer.channel_layer.group_send(
            space.channel_group,
            {
                "type": "broadcast_presence_focus",
                "payload": payload,
                "ignore_web_socket_id": self._web_socket_id,
                "focus_type": focus_type_name,
            },
        )

    @staticmethod
    def _has_auth_members(members: list[ActivePresenceEntry]) -> bool:
        return any(m["user_id"] != ANONYMOUS_USER_ID for m in members)

    async def _signal_editors_active(self, space: PresenceSpace, active: bool) -> None:
        await self._broadcast(
            space,
            {
                "type": "presence.editors_active",
                "space": space.name,
                "active": active,
            },
        )

    async def _send_editors_active(self, space: PresenceSpace, active: bool) -> None:
        await self._consumer.send_json(
            {
                "type": "presence.editors_active",
                "space": space.name,
                "active": active,
            }
        )

    async def _maybe_signal_last_editor_left(self, space: PresenceSpace) -> None:
        if self.user_id == ANONYMOUS_USER_ID:
            return
        remaining = await space.get_members()
        if not self._has_auth_members(remaining):
            await self._signal_editors_active(space, active=False)

    def _filter_members_focus(
        self,
        page_type_name: str,
        parameters: dict,
        members: list[ActivePresenceEntry],
    ) -> list[ActivePresenceEntry]:
        """
        Apply the recipient-side focus filter to a members snapshot, mirroring
        the live path in ``receive_focus_broadcast``. Member visibility is
        never affected: a focus that cannot be positively cleared for delivery
        is nulled out instead (fails closed).

        :param page_type_name: The recipient's registered page type name.
        :param parameters: The recipient's page subscription parameters.
        :param members: The members snapshot with stored focus payloads.
        :return: The snapshot with each focus filtered for this recipient.
        """

        return [
            {
                **member,
                "focus": self._filter_member_focus(
                    page_type_name, parameters, member["focus"]
                ),
            }
            for member in members
        ]

    @staticmethod
    def _filter_member_focus(
        page_type_name: str,
        parameters: dict,
        focus: dict | None,
    ) -> Optional[dict]:
        """
        Return the focus if the recipient page grants visibility, otherwise
        None. Any resolution failure or filter error also yields None so a
        stored focus is never leaked to a recipient that was not positively
        cleared to see it.

        :param page_type_name: The recipient's registered page type name.
        :param parameters: The recipient's page subscription parameters.
        :param focus: The stored focus payload, or None.
        :return: The focus payload if visible to the recipient, else None.
        """

        if focus is None:
            return None
        try:
            page_type = page_registry.get(page_type_name)
            focus_type = presence_focus_type_registry.get(focus["type"])
        except (
            page_registry.does_not_exist_exception_class,
            presence_focus_type_registry.does_not_exist_exception_class,
            KeyError,
            TypeError,
        ):
            return None
        try:
            if page_type.filter_focus_for_recipient(parameters, focus, focus_type):
                return focus
        except Exception:
            logger.exception("Focus filtering failed for page type {}", page_type_name)
        return None

    async def receive_focus_broadcast(self, event: dict) -> None:
        """
        Filter and deliver an incoming focus broadcast to this connection.
        Called by the consumer's channel-layer handler.

        :param event: The channel layer event containing payload and focus_type.
        """

        payload = event["payload"]
        focus = payload.get("focus")

        focus_type_name = event.get("focus_type")
        focus_type = None
        if focus_type_name:
            try:
                focus_type = presence_focus_type_registry.get(focus_type_name)
            except presence_focus_type_registry.does_not_exist_exception_class:
                return

        space_name = payload["space"]
        recipient_pages = self.get_recipient_pages_for_space(space_name)
        if not recipient_pages:
            return

        for page_type_name, page_params in recipient_pages:
            try:
                page_type = page_registry.get(page_type_name)
            except page_registry.does_not_exist_exception_class:
                continue

            try:
                should_deliver = page_type.filter_focus_for_recipient(
                    page_params, focus, focus_type
                )
            except Exception:
                logger.exception(
                    "Focus filtering failed for page type {}", page_type_name
                )
                continue

            if should_deliver:
                await self._consumer.send_json(payload)
                return

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
