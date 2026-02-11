"""
MCP Session Management Module

This module provides session management for MCP SSE connections, including:
- Session state tracking across reconnections
- Request validation based on initialization state
- Session cleanup and lifecycle management
- Thread-safe session registry for concurrent connections

The session manager ensures that MCP requests are only processed after proper
initialization, preventing "Received request before initialization was complete"
errors that occur during backend restarts or reconnection scenarios.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from baserow.core.mcp.lifecycle import (
    MCPSessionLifecycle,
    MCPSessionRegistry,
    MCPSessionState,
)

logger = logging.getLogger(__name__)


@dataclass
class MCPSessionMetrics:
    """Metrics for monitoring MCP session health and behavior."""

    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    requests_received: int = 0
    requests_dropped: int = 0
    requests_processed: int = 0
    initialization_attempts: int = 0


@dataclass
class MCPSession:
    """
    Represents an active MCP SSE session with full lifecycle tracking.
    
    This class wraps MCPSessionLifecycle with additional metadata and metrics
    to provide comprehensive session management across backend restarts.
    """

    session_id: UUID
    lifecycle: MCPSessionLifecycle
    metrics: MCPSessionMetrics = field(default_factory=MCPSessionMetrics)
    endpoint_key: Optional[str] = None
    
    def record_request(self, method: str, is_dropped: bool = False) -> None:
        """Record a request for metrics tracking."""
        self.metrics.last_activity = datetime.now()
        self.metrics.requests_received += 1
        
        if is_dropped:
            self.metrics.requests_dropped += 1
        else:
            self.metrics.requests_processed += 1
        
        if method == "initialize":
            self.metrics.initialization_attempts += 1
    
    def should_forward_request(self, payload: Dict[str, Any]) -> bool:
        """
        Determine if a request should be forwarded to the MCP server.
        
        This is the key method that prevents premature requests from reaching
        the MCP server before initialization completes.
        
        :param payload: The parsed JSON-RPC payload
        :return: True if request should be forwarded, False if it should be dropped
        """
        method = payload.get("method", "unknown")
        should_forward = self.lifecycle.on_client_payload(payload)
        
        if not should_forward:
            logger.warning(
                f"Session {self.session_id}: Dropping premature request '{method}' "
                f"in state {self.lifecycle.state}. "
                f"Requests received: {self.metrics.requests_received}, "
                f"dropped: {self.metrics.requests_dropped}"
            )
        
        self.record_request(method, is_dropped=not should_forward)
        return should_forward
    
    def track_server_response(self, payload: Dict[str, Any]) -> None:
        """Track server responses to update session state."""
        self.lifecycle.on_server_payload(payload)
        self.metrics.last_activity = datetime.now()
    
    @property
    def state(self) -> MCPSessionState:
        """Current session state."""
        return self.lifecycle.state
    
    @property
    def is_initialized(self) -> bool:
        """Check if session is fully initialized and ready for requests."""
        return self.lifecycle.state == MCPSessionState.INITIALIZED
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of session metrics for logging/monitoring."""
        return {
            "session_id": self.session_id.hex,
            "state": self.state.value,
            "endpoint_key": self.endpoint_key,
            "created_at": self.metrics.created_at.isoformat(),
            "last_activity": self.metrics.last_activity.isoformat(),
            "requests_received": self.metrics.requests_received,
            "requests_dropped": self.metrics.requests_dropped,
            "requests_processed": self.metrics.requests_processed,
            "initialization_attempts": self.metrics.initialization_attempts,
        }


class MCPSessionManager:
    """
    Global session manager for all MCP SSE connections.
    
    This manager provides a high-level API for session lifecycle management,
    wrapping the lower-level MCPSessionRegistry with additional features like
    metrics tracking and session metadata.
    """

    def __init__(self):
        self._registry = MCPSessionRegistry()
        self._sessions: Dict[str, MCPSession] = {}
        logger.info("MCPSessionManager initialized")
    
    def create_session(
        self, session_id: UUID, endpoint_key: Optional[str] = None
    ) -> MCPSession:
        """
        Create and register a new MCP session.
        
        :param session_id: Unique identifier for the session
        :param endpoint_key: Optional endpoint key for tracking
        :return: The created MCPSession instance
        """
        lifecycle = self._registry.register(session_id)
        session = MCPSession(
            session_id=session_id,
            lifecycle=lifecycle,
            endpoint_key=endpoint_key,
        )
        self._sessions[session_id.hex] = session
        
        logger.info(
            f"Created MCP session {session_id.hex} "
            f"for endpoint {endpoint_key or 'unknown'}"
        )
        return session
    
    def get_session(self, session_id: UUID) -> Optional[MCPSession]:
        """
        Retrieve an existing session by ID.
        
        :param session_id: The session identifier
        :return: The MCPSession if found, None otherwise
        """
        return self._sessions.get(session_id.hex)
    
    def close_session(self, session_id: UUID) -> None:
        """
        Close and cleanup a session.
        
        :param session_id: The session identifier to close
        """
        session = self._sessions.pop(session_id.hex, None)
        self._registry.unregister(session_id)
        
        if session:
            metrics = session.get_metrics_summary()
            logger.info(
                f"Closed MCP session {session_id.hex}: {metrics}"
            )
        else:
            logger.debug(f"Attempted to close non-existent session {session_id.hex}")
    
    def get_active_session_count(self) -> int:
        """Get the number of currently active sessions."""
        return len(self._sessions)
    
    def get_all_sessions_metrics(self) -> list[Dict[str, Any]]:
        """Get metrics for all active sessions."""
        return [session.get_metrics_summary() for session in self._sessions.values()]


# Global singleton instance
_session_manager = MCPSessionManager()


def get_session_manager() -> MCPSessionManager:
    """
    Get the global MCPSessionManager instance.
    
    This function provides access to the singleton session manager used
    throughout the MCP SSE transport layer.
    """
    return _session_manager
