from typing import Any, TypedDict, Union


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
