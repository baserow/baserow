import json
from typing import Any, Optional

from baserow.core.registry import Instance

DEFAULT_MAX_FOCUS_BYTES = 2048


class InvalidPresenceFocus(Exception):
    """Consumer silently drops the message (no broadcast, no error to sender)."""


class PresenceFocusType(Instance):
    """Subclasses must set ``declared_keys`` — only those keys survive
    validation (allowlist). Extra keys from the client are stripped."""

    max_focus_bytes: int = DEFAULT_MAX_FOCUS_BYTES
    declared_keys: tuple[str, ...] = ("type",)

    def validate(self, focus: Any) -> dict:
        """Validate focus payload. Returns sanitized copy with only
        ``declared_keys``. Raises ``InvalidPresenceFocus`` on failure."""

        if not isinstance(focus, dict):
            raise InvalidPresenceFocus("focus must be an object")
        if focus.get("type") != self.type:
            raise InvalidPresenceFocus(
                f"focus type mismatch: expected {self.type!r}, "
                f"got {focus.get('type')!r}"
            )
        try:
            encoded = json.dumps(focus, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise InvalidPresenceFocus("focus is not JSON-serializable") from exc
        if len(encoded.encode("utf-8")) > self.max_focus_bytes:
            raise InvalidPresenceFocus("focus payload too large")
        return {k: focus[k] for k in self.declared_keys if k in focus}

    def filter_for_recipient(
        self, focus: dict, recipient_context: dict
    ) -> Optional[dict]:
        """Return the focus that ``recipient_context`` should see, or
        None to suppress. Default is identity (pass through)."""

        return focus


