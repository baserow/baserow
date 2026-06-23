from typing import Any, NamedTuple, TypedDict


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
