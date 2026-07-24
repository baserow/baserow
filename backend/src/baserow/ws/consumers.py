from dataclasses import dataclass
from operator import attrgetter
from typing import TYPE_CHECKING, Any, Optional

from django.conf import settings

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from loguru import logger
from opentelemetry import metrics

from baserow.config.settings.utils import try_int
from baserow.ws.presence import (
    ANONYMOUS_ALLOWED_PRESENCE_EVENTS,
    ANONYMOUS_USER_ID,
    PRESENCE_EVENT_PREFIX,
    NullPresenceHandler,
    PresenceHandler,
    PresenceHandlerProtocol,
    make_page_key,
)
from baserow.ws.realtime_events import (
    FIRST_CONNECT_CURSOR,
    NO_REPLAY_AVAILABLE,
    RealtimeEventHandler,
    ReplayEventsResult,
)
from baserow.ws.registries import (
    PageType,
    page_registry,
)

MSG_TYPE_REPLAY_EVENTS = "replay_events"
MSG_TYPE_PRESENCE_FOCUS = "presence.focus"

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from baserow.ws.models import RealtimeEvent
    from baserow.ws.types import (
        BroadcastToChannelGroupMessage,
        BroadcastToUsersIndividualPayloadsMessage,
        BroadcastToUsersMessage,
        ForceDisconnectMessage,
    )


meter = metrics.get_meter(__name__)
websocket_connections_counter = meter.create_counter(
    "baserow.websocket_connections",
    unit="1",
    description="Accepted realtime WebSocket connections.",
)
websocket_disconnects_counter = meter.create_counter(
    "baserow.websocket_disconnects",
    unit="1",
    description="Closed realtime WebSocket connections, labelled by close code.",
)
websocket_active_connections = meter.create_up_down_counter(
    "baserow.websocket_active_connections",
    unit="1",
    description="Currently open realtime WebSocket connections.",
)

# Known close codes pass through; anything else becomes "other" to keep the
# metric's label cardinality bounded.
_KNOWN_WEBSOCKET_CLOSE_CODES = frozenset(range(1000, 1016))


def _bucket_close_code(code: Optional[int]) -> str:
    return str(code) if code in _KNOWN_WEBSOCKET_CLOSE_CODES else "other"


@dataclass
class PageContext:
    """
    The context about a page and a user when the user
    intends to be subscribed or unsubscribed from
    getting changes relevant to the page.
    """

    web_socket_id: str
    user: Optional["AbstractUser"]
    resolved_page_type: PageType
    page_scope: "PageScope"


@dataclass
class PageScope:
    """
    Represents one page that a user can be subscribed to.
    Different page parameters can be used to represent
    subscriptions to the same page types with different
    values (e.g. being subscribed to a table page with
    table_id=1 or table_id=2)
    """

    page_type: str
    page_parameters: dict[str, Any]


class SubscribedPages:
    """
    Holds information about all pages a user is subscribed to.
    """

    def __init__(self):
        self.pages: list[PageScope] = []

    def add(self, page_scope: PageScope):
        """
        Adds a page to the list of subscribed pages.

        :param page_scope: Page to add.
        """

        if page_scope not in self.pages:
            self.pages.append(page_scope)

    def remove(self, page_scope: PageScope):
        """
        Removes a page from the list of subscribed pages.

        :param page_scope: Page to remove.
        """

        try:
            self.pages.remove(page_scope)
        except ValueError:
            pass

    def is_page_in_permission_group(
        self, page_scope: PageScope, group_name_to_check: str
    ) -> bool:
        """
        Checks whether an instance of PageScope belongs to the provided
        permission group.

        :param page_scope: The page to check.
        :param group_name_to_check: The permission group name that will be
            compared to permission group name of the page.
        :return: True if the page has the same permission group name.
        """

        try:
            page_type = page_registry.get(page_scope.page_type)
        except page_registry.does_not_exist_exception_class:
            return False

        page_perm_group_name = page_type.get_permission_channel_group_name(
            **page_scope.page_parameters
        )
        if page_perm_group_name == group_name_to_check:
            return True
        return False

    def has_pages_with_permission_group(self, group_name_to_check: str) -> bool:
        """
        Utility method that determines whether the list of subscribed
        pages contains any page with the provided permission group.

        This is useful to know for consumers using this class to determine
        if by unsubscribing to a page they should unsubscribe from a
        permission group as well or there are still pages that need the
        same permission group.

        :param group_name_to_check: The permission group name that will be
            compared to permission group names of the subscribed pages.
        :return: True if the list of subscribed pages contains any page matching
            the provided permission group name.
        """

        return any(
            self.is_page_in_permission_group(page, group_name_to_check)
            for page in self.pages
        )

    def copy(self):
        new = SubscribedPages()
        new.pages = self.pages.copy()
        return new

    def __len__(self):
        return len(self.pages)

    def __iter__(self):
        return iter(self.pages)


class CoreConsumer(AsyncJsonWebsocketConsumer):
    presence: PresenceHandlerProtocol = NullPresenceHandler()

    async def connect(self):
        await self.accept()
        websocket_connections_counter.add(1)
        websocket_active_connections.add(1)

        user = self.scope["user"]
        await self.send_json(
            {
                "type": "authentication",
                "success": user is not None,
                # Kept for backwards compatibility.
                "web_socket_id": self.scope["web_socket_id"],
                "replay_enabled": user is not None
                and getattr(user, "is_authenticated", False)
                and RealtimeEventHandler.is_recording_enabled(),
            }
        )

        if not user:
            await self.close()
            return

        self.scope["pages"] = SubscribedPages()
        web_socket_id = self.scope["web_socket_id"]
        if settings.PRESENCE_VISIBLE_USERS > 0:
            user_id = (
                user.id
                if getattr(user, "is_authenticated", False)
                else ANONYMOUS_USER_ID
            )
            self.presence = PresenceHandler(
                consumer=self,
                web_socket_id=web_socket_id,
                user_id=user_id,
            )
        else:
            self.presence = NullPresenceHandler()
        await self.channel_layer.group_add("users", self.channel_name)

    async def disconnect(self, code):
        # Record the disconnect in a finally block so the counter still fires if
        # cleanup raises (e.g. a Redis hiccup in group_discard). Otherwise the
        # eager connect counter would drift ahead during infrastructure failures,
        # exactly when the metric matters most.
        try:
            await self.presence.leave_all_spaces()
            await self._discard_all_channel_groups()
            await self.channel_layer.group_discard("users", self.channel_name)
        finally:
            websocket_active_connections.add(-1)
            websocket_disconnects_counter.add(
                1, attributes={"code": _bucket_close_code(code)}
            )

    async def receive_json(self, content, **parameters):
        """
        Processes incoming messages.
        """
        msg_type = content.get("type", "")

        if msg_type == MSG_TYPE_REPLAY_EVENTS:
            await self._handle_replay_events(content)
            return

        if msg_type == MSG_TYPE_PRESENCE_FOCUS:
            await self._handle_presence_focus(content)
            return

        if "page" in content:
            await self._add_page_scope(content)
        if "remove_page" in content:
            await self._remove_page_scope(content)

    async def _get_page_context(
        self, content: dict, page_name_attr: str
    ) -> Optional[PageContext]:
        """
        Helper method that will construct a PageContext object for adding
        or removing page scopes from the consumer.

        :param content: Dictionary representing the JSON that the client sent.
        :param page_name_attr: Identifies the name of the parameter in the
            content dictionary that refers to the page type.
        """

        user = self.scope["user"]
        web_socket_id = self.scope["web_socket_id"]

        if not user:
            return None

        try:
            page_type = page_registry.get(content[page_name_attr])
        except page_registry.does_not_exist_exception_class:
            return None

        parameters = {
            parameter: content.get(parameter) for parameter in page_type.parameters
        }

        return PageContext(
            page_scope=PageScope(
                page_type=content[page_name_attr],
                page_parameters=parameters,
            ),
            resolved_page_type=page_type,
            user=user,
            web_socket_id=web_socket_id,
        )

    async def _add_page_scope(self, content: dict):
        """
        Subscribes the connection to a page abstraction. Based on the provided page
        type we can figure out to which page the connection wants to subscribe to. This
        is for example used when the users visits a page that they might want to
        receive real time updates for.

        :param content: The provided payload by the user. This should contain the page
            type and additional parameters.
        """

        context = await self._get_page_context(content, "page")

        if not context:
            return

        user, web_socket_id, page_type, parameters = attrgetter(
            "user", "web_socket_id", "resolved_page_type", "page_scope.page_parameters"
        )(context)

        can_add = await database_sync_to_async(page_type.can_add)(
            user, web_socket_id, **parameters
        )

        if not can_add:
            return

        group_name = page_type.get_group_name(**parameters)
        await self.channel_layer.group_add(group_name, self.channel_name)

        permission_group_name = page_type.get_permission_channel_group_name(
            **parameters
        )
        if permission_group_name:
            await self.channel_layer.group_add(permission_group_name, self.channel_name)

        page_scope = PageScope(page_type=page_type.type, page_parameters=parameters)
        self.scope["pages"].add(page_scope)

        await self.send_json(
            {
                "type": "page_add",
                "page": page_type.type,
                "parameters": parameters,
            }
        )

        await self.presence.handle_page_subscribed(page_type.type, parameters)

    async def _remove_page_scope(self, content: dict, send_confirmation=True):
        """
        Unsubscribes the connection from a page. Based on the provided page
        type and its params we can figure out to which page the connection wants
        to unsubscribe from.

        :param content: The provided payload by the user. This should contain the page
            type and additional parameters.
        :param send_confirmation: If True, the client will receive a confirmation
            message about unsubscribing.
        """

        context = await self._get_page_context(content, "remove_page")

        if not context:
            return

        page_type, parameters = attrgetter(
            "resolved_page_type", "page_scope.page_parameters"
        )(context)

        group_name = page_type.get_group_name(**parameters)
        await self.channel_layer.group_discard(group_name, self.channel_name)

        page_scope = PageScope(page_type=page_type.type, page_parameters=parameters)
        self.scope["pages"].remove(page_scope)

        await self.presence.handle_page_unsubscribed(page_type.type, parameters)

        permission_group_name = page_type.get_permission_channel_group_name(
            **parameters
        )
        if permission_group_name and not self.scope[
            "pages"
        ].has_pages_with_permission_group(permission_group_name):
            await self.channel_layer.group_discard(
                permission_group_name, self.channel_name
            )

        if send_confirmation:
            await self.send_json(
                {
                    "type": "page_discard",
                    "page": page_type.type,
                    "parameters": parameters,
                }
            )

    async def _remove_all_page_scopes(self, send_confirmation=True):
        """
        Unsubscribes the connection from all currently subscribed pages.
        Used for live connections (e.g. permission revocation that affects
        all pages). For disconnect cleanup, use _discard_all_channel_groups.
        """

        if self.scope.get("pages"):
            for page_scope in self.scope["pages"].copy():
                try:
                    content = {
                        "user": self.scope["user"],
                        "web_socket_id": self.scope["web_socket_id"],
                        "remove_page": page_scope.page_type,
                        **page_scope.page_parameters,
                    }
                    await self._remove_page_scope(
                        content, send_confirmation=send_confirmation
                    )
                except Exception:
                    logger.exception(
                        "Failed to remove page scope {} during cleanup",
                        page_scope.page_type,
                    )

    async def _discard_all_channel_groups(self) -> None:
        """
        Tears down all channel group memberships without sending client
        messages or touching presence. Used during disconnect — presence
        cleanup is handled separately by leave_all_spaces().
        """

        if not self.scope.get("pages"):
            return

        for page_scope in self.scope["pages"].copy():
            try:
                page_type = page_registry.get(page_scope.page_type)
                group_name = page_type.get_group_name(**page_scope.page_parameters)
                await self.channel_layer.group_discard(group_name, self.channel_name)
                perm = page_type.get_permission_channel_group_name(
                    **page_scope.page_parameters
                )
                if perm:
                    await self.channel_layer.group_discard(perm, self.channel_name)
            except Exception:
                logger.exception(
                    "Failed to discard channel groups for page scope {} "
                    "during disconnect",
                    page_scope.page_type,
                )

    async def _remove_page_scopes_associated_with_perm_group(
        self, permission_group_name: str
    ):
        """
        Unsubscribes the connection from all currently subscribed pages associated
        with the provided permission channel group.

        :param permission_group_name: The name of the permission channel group.
        """

        if self.scope.get("pages"):
            for page_scope in self.scope["pages"].copy():
                if self.scope["pages"].is_page_in_permission_group(
                    page_scope, permission_group_name
                ):
                    content = {
                        "user": self.scope["user"],
                        "web_socket_id": self.scope["web_socket_id"],
                        "remove_page": page_scope.page_type,
                        **page_scope.page_parameters,
                    }
                    await self._remove_page_scope(content, send_confirmation=True)

    async def _replay_persisted_events(self, events: list["RealtimeEvent"]) -> bool:
        """
        Re-deliver persisted events through the normal broadcast handlers.

        :param events: Ordered events to replay to this websocket connection.
        :return: Whether every event could be replayed. If False, the client should be
            forced to refresh because some events could not be replayed.
        """

        replay_plan = []
        for event in events:
            event_type = event.payload.get("type", "")
            if not isinstance(event_type, str) or not event_type.startswith(
                "broadcast_to_"
            ):
                logger.bind(
                    realtime_event_id=event.id,
                    channel_group=event.channel_group,
                    event_type=event_type,
                ).error("Cannot replay realtime event with unsupported payload type.")
                return False

            handler = getattr(self, event_type, None)
            if handler is None:
                logger.bind(
                    realtime_event_id=event.id,
                    channel_group=event.channel_group,
                    event_type=event_type,
                ).error("Cannot replay realtime event because its handler is missing.")
                return False

            replay_plan.append((event, handler))

        for event, handler in replay_plan:
            RealtimeEventHandler.add_event_id_to_payload(event.id, event.payload)
            await handler(event.payload)

        return True

    @staticmethod
    def _parse_last_seen_id(content: dict) -> int:
        """
        Extract and validate the ``last_seen_id`` cursor from a
        ``replay_events`` message. Values below ``NO_REPLAY_AVAILABLE``
        are normalised to ``FIRST_CONNECT_CURSOR`` (safe default).

        :param content: The JSON payload sent by the websocket client.
        :return: ``FIRST_CONNECT_CURSOR`` for a fresh session or
            missing/invalid input, ``NO_REPLAY_AVAILABLE`` when the client
            has no usable high-water mark, or the positive event id the
            client last processed.
        """

        last_seen_id = try_int(content.get("last_seen_id"))
        if last_seen_id is None or last_seen_id < NO_REPLAY_AVAILABLE:
            return FIRST_CONNECT_CURSOR
        return last_seen_id

    async def _send_replay_events_result(self, result: ReplayEventsResult) -> None:
        """
        Send the replay decision to the websocket client.

        :param result: The replay decision produced by ``RealtimeEventHandler``.
        """

        await self.send_json(
            {
                "type": "replay_events_result",
                "force_refresh": result.force_refresh,
                "latest_event_id": result.latest_event_id,
            }
        )

    async def _handle_replay_events(self, content: dict):
        """
        Handle ``replay_events`` from the frontend.

        Visible outcomes: baseline (``FIRST_CONNECT_CURSOR``), replay since
        ``last_seen_id``, or ``force_refresh=true`` when the gap is too
        large, the cursor expired, the client has no high-water mark,
        replay failed mid-flight, or recording is disabled.
        Silent drops: unauthenticated requests only.
        """

        user = self.scope.get("user")
        if user is None or not getattr(user, "is_authenticated", False):
            return

        if not RealtimeEventHandler.is_recording_enabled():
            await self._send_replay_events_result(
                ReplayEventsResult(
                    force_refresh=True,
                    latest_event_id=NO_REPLAY_AVAILABLE,
                    replay_events=[],
                )
            )
            return

        last_seen_id = self._parse_last_seen_id(content)
        web_socket_id = self.scope.get("web_socket_id")

        pages = self.scope.get("pages", SubscribedPages())
        page_group_names = RealtimeEventHandler.get_page_group_names(pages)

        result = await database_sync_to_async(
            RealtimeEventHandler.get_replay_events_result
        )(user.id, page_group_names, last_seen_id, web_socket_id)

        if result.replay_events and not await self._replay_persisted_events(
            result.replay_events
        ):
            result = ReplayEventsResult(
                force_refresh=True,
                latest_event_id=NO_REPLAY_AVAILABLE,
                replay_events=[],
            )
        await self._send_replay_events_result(result)

    # Event handlers

    async def force_disconnect_users(self, event: "ForceDisconnectMessage"):
        """
        Closes the connection with this user if their user id is in the provided
        list.

        :param event: The event containing the payload: the user ids that must
            be disconnected and optionally the web socket ids to ignore from
            disconnection.
        """

        disconnect_user_ids = event["user_ids"]
        ignore_web_socket_ids = event["ignore_web_socket_ids"] or []

        user_id = self.scope["user"].id
        web_socket_id = self.scope["web_socket_id"]

        if (
            user_id in disconnect_user_ids
            and web_socket_id not in ignore_web_socket_ids
        ):
            await self.send_json({"type": "force_disconnect"})
            return await self.close()

    async def broadcast_to_users(self, event: "BroadcastToUsersMessage"):
        """
        Broadcasts a message to all the users that are in the provided user_ids list.
        Optionally the ignore_web_socket_id is ignored because that is often the
        sender. Also, if `send_to_all_users` is set to True then all users will be sent
        the payload regardless of `user_ids`, but `ignore_web_socket_id` will still
        be respected.

        :param event: The event containing the payload, user ids and the web socket
            id that must be ignored.
        """

        web_socket_id = self.scope["web_socket_id"]
        payload = event["payload"]
        ignore_web_socket_id = event["ignore_web_socket_id"]

        shouldnt_ignore = (
            not ignore_web_socket_id or ignore_web_socket_id != web_socket_id
        )
        if shouldnt_ignore and RealtimeEventHandler.should_deliver_users_channel_event(
            self.scope["user"].id,
            event,
        ):
            await self.send_json(payload)

    async def broadcast_to_users_individual_payloads(
        self, event: "BroadcastToUsersIndividualPayloadsMessage"
    ):
        """
        Accepts a payload mapping and sends the payload as JSON if the user_id of the
        consumer is part of the mapping provided

        :param event: The event containing the payload mapping
        """

        web_socket_id = self.scope["web_socket_id"]

        payload_map = event["payload_map"]
        ignore_web_socket_id = event["ignore_web_socket_id"]

        user_id = str(self.scope["user"].id)

        shouldnt_ignore = (
            not ignore_web_socket_id or ignore_web_socket_id != web_socket_id
        )

        if shouldnt_ignore and RealtimeEventHandler.should_deliver_users_channel_event(
            self.scope["user"].id,
            event,
        ):
            await self.send_json(payload_map[user_id])

    async def broadcast_to_group(self, event: "BroadcastToChannelGroupMessage"):
        """
        Broadcasts a message to all the users that are in the provided group name.

        :param event: The event containing the payload, group name and the web socket
            id that must be ignored.
        """

        web_socket_id = self.scope["web_socket_id"]
        payload = event["payload"]
        ignore_web_socket_id = event["ignore_web_socket_id"]
        exclude_user_ids = set(event.get("exclude_user_ids", None) or [])
        user = self.scope["user"]

        if not getattr(user, "is_authenticated", False):
            payload_type = payload.get("type", "")
            if (
                payload_type.startswith(PRESENCE_EVENT_PREFIX)
                and payload_type not in ANONYMOUS_ALLOWED_PRESENCE_EVENTS
            ):
                return

        if getattr(user, "id", None) in exclude_user_ids:
            return

        if not ignore_web_socket_id or ignore_web_socket_id != web_socket_id:
            await self.send_json(payload)

    async def _handle_presence_focus(self, content: dict[str, Any]) -> None:
        """
        Handle an incoming ``presence.focus`` message from the client.
        Resolves the page type and parameters, builds the page key, and
        delegates to the presence handler for validation + broadcast.

        :param content: The decoded JSON message from the WebSocket client.
        """

        page_type_name = content.get("page")
        if not page_type_name:
            return

        try:
            page_type = page_registry.get(page_type_name)
        except page_registry.does_not_exist_exception_class:
            return

        parameters = {param: content.get(param) for param in page_type.parameters}
        page_key = make_page_key(page_type_name, parameters)
        await self.presence.handle_focus(page_key, content.get("focus"))

    async def broadcast_presence_focus(self, event: dict[str, Any]) -> None:
        """
        Channel-layer handler for focus broadcasts. Focus events are
        ephemeral — not persisted by RealtimeEventHandler and not replayed
        on reconnect. Uses a dedicated message type (not ``broadcast_to_group``)
        so that recipient-side filtering can be applied per page type.

        :param event: The channel-layer event dict containing the focus payload.
        """

        web_socket_id = self.scope.get("web_socket_id")
        ignore_web_socket_id = event.get("ignore_web_socket_id")
        if ignore_web_socket_id and ignore_web_socket_id == web_socket_id:
            return

        await self.presence.receive_focus_broadcast(event)

    async def users_removed_from_permission_group(self, event: dict) -> None:
        """
        Event handler that reacts to a situation when one or many users were
        revoked access to resources associated with a permission channel group.

        When that happens the consumer has to check whether it is the consumer of
        the involved user and if so, remove itself from all pages associated with
        the permission channel group.
        """

        user_ids_to_remove = event["user_ids_to_remove"]
        user_id = self.scope["user"].id

        if user_id in user_ids_to_remove:
            await self._remove_page_scopes_associated_with_perm_group(
                event["permission_group_name"]
            )
