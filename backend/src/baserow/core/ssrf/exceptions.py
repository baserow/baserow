from __future__ import annotations

from typing import Optional


class SSRFException(Exception):
    """Base exception for SSRF protection."""


class InvalidSSRFAddress(SSRFException):
    """Raised when a resolved address fails SSRF validation."""

    def __init__(
        self,
        address: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        if message:
            super().__init__(message)
        elif address:
            super().__init__(f"Address {address} is not allowed")
        else:
            super().__init__("Address is not allowed")
        self.address = address
