import json
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Any
from uuid import UUID


class MCPSessionState(str, Enum):
    AWAITING_INITIALIZE = "awaiting_initialize"
    AWAITING_INITIALIZED_NOTIFICATION = "awaiting_initialized_notification"
    INITIALIZED = "initialized"


@dataclass
class MCPSessionLifecycle:
    state: MCPSessionState = MCPSessionState.AWAITING_INITIALIZE
    initialize_request_id: str | int | None = None

    def on_client_payload(self, payload: dict[str, Any]) -> bool:
        """
        Returns whether the incoming client payload should be forwarded to the MCP
        runtime.
        """

        method = payload.get("method")
        if method is None:
            # Client -> server payloads are expected to be requests/notifications.
            # We still pass through unknown structures to let normal JSON-RPC
            # validation handle them.
            return True

        request_id = payload.get("id")
        is_request = request_id is not None
        is_initialize = method == "initialize"
        is_initialized_notification = method == "notifications/initialized"

        if is_initialize and is_request:
            # Support repeated initialize attempts by replacing the currently tracked
            # request id.
            self.initialize_request_id = request_id
            self.state = MCPSessionState.AWAITING_INITIALIZED_NOTIFICATION
            return True

        if is_initialized_notification:
            self.state = MCPSessionState.INITIALIZED
            return True

        if not is_request:
            # Allow other notifications in all phases.
            return True

        # Any request that is not initialize is unsafe before the session has fully
        # completed initialization.
        return self.state == MCPSessionState.INITIALIZED

    def on_server_payload(self, payload: dict[str, Any]) -> None:
        """
        Observe server -> client payloads. This currently only tracks re-initialization
        behavior and does not block outgoing traffic.
        """

        if (
            self.initialize_request_id is not None
            and payload.get("id") == self.initialize_request_id
            and "result" in payload
        ):
            # We keep waiting for notifications/initialized before marking as ready.
            self.state = MCPSessionState.AWAITING_INITIALIZED_NOTIFICATION


class MCPSessionRegistry:
    def __init__(self):
        self._sessions: dict[str, MCPSessionLifecycle] = {}
        self._lock = Lock()

    @staticmethod
    def _key(session_id: UUID) -> str:
        return session_id.hex

    def register(self, session_id: UUID) -> MCPSessionLifecycle:
        with self._lock:
            lifecycle = MCPSessionLifecycle()
            self._sessions[self._key(session_id)] = lifecycle
            return lifecycle

    def unregister(self, session_id: UUID) -> None:
        with self._lock:
            self._sessions.pop(self._key(session_id), None)

    def get(self, session_id: UUID) -> MCPSessionLifecycle | None:
        with self._lock:
            return self._sessions.get(self._key(session_id))


def parse_json_payload(raw_payload: bytes | str) -> dict[str, Any] | None:
    if isinstance(raw_payload, bytes):
        payload = raw_payload.decode("utf-8")
    else:
        payload = raw_payload

    try:
        parsed = json.loads(payload)
    except (TypeError, ValueError):
        return None

    if not isinstance(parsed, dict):
        return None
    return parsed


def is_runtime_error_in_exception_group(
    exception: BaseException, message_fragment: str
) -> bool:
    if isinstance(exception, RuntimeError) and message_fragment in str(exception):
        return True

    if isinstance(exception, BaseExceptionGroup):
        return any(
            is_runtime_error_in_exception_group(sub_exception, message_fragment)
            for sub_exception in exception.exceptions
        )

    return False
