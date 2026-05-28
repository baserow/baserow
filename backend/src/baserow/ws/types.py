from typing import Any, NamedTuple, TypedDict, Union


class ChannelGroupMessage(NamedTuple):
    """
    A single channel-layer ``message`` paired with the ``channel_group_name``
    it should be broadcast to. Being a ``NamedTuple`` it unpacks as a
    ``(channel_group_name, message)`` tuple wherever that is expected.
    """

    channel_group_name: str
    message: dict


class ForceDisconnectMessage(TypedDict, total=False):
    type: str
    user_ids: list[int]
    ignore_web_socket_ids: list[str] | None


class BroadcastToUsersMessage(TypedDict, total=False):
    type: str
    user_ids: list[int]
    payload: dict[str, Any]
    ignore_web_socket_id: str | None
    send_to_all_users: bool


class BroadcastToChannelGroupMessage(TypedDict, total=False):
    type: str
    payload: dict[str, Any]
    ignore_web_socket_id: str | None
    exclude_user_ids: list[int] | None


PayloadMap = dict[str, Any]


class BroadcastToUsersIndividualPayloadsMessage(TypedDict, total=False):
    type: str
    payload_map: PayloadMap
    ignore_web_socket_id: str | None


RealtimeEventPayload = Union[
    BroadcastToUsersMessage,
    BroadcastToChannelGroupMessage,
    BroadcastToUsersIndividualPayloadsMessage,
]


class PageSubscribeContent(TypedDict, total=False):
    page: str


class PageUnsubscribeContent(TypedDict, total=False):
    remove_page: str


class RealtimeSubscribeContent(TypedDict, total=False):
    type: str
    workspace_id: int | None
    last_seen_id: int | None


class PresenceFocusContent(TypedDict, total=False):
    type: str
    page: str
    focus: dict[str, Any] | None


class PresenceEntry(TypedDict):
    user_id: int
    focus: dict[str, Any] | None
    last_seen: int


class PresenceSnapshotEntry(TypedDict):
    user_id: int
    web_socket_id: str
    focus: dict[str, Any] | None


class PresenceJoinMessage(TypedDict):
    type: str
    channel: str
    user_id: int
    web_socket_id: str


class PresenceLeaveMessage(TypedDict):
    type: str
    channel: str
    user_id: int
    web_socket_id: str


class PresenceFocusMessage(TypedDict):
    type: str
    channel: str
    user_id: int
    web_socket_id: str
    focus: dict[str, Any] | None
