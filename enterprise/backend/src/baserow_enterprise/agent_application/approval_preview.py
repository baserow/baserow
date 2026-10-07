"""
Builds the human-readable preview stored with a tool approval: the email or
message an action tool would send, resolved from the model's inputs, or the
rows a workspace tool would write.
"""

import re
from typing import Any, Optional

from loguru import logger

from .agent_dispatch_context import AgentDispatchContext

_ROW_TOOL_RE = re.compile(r"^(create|update|delete)_rows_in_table_(\d+)$")
_EMAIL_SERVICE_TYPES = {"smtp_email"}
_EMAIL_FIELDS = (
    ("from", "from_email"),
    ("from_name", "from_name"),
    ("to", "to_emails"),
    ("cc", "cc_emails"),
    ("bcc", "bcc_emails"),
    ("subject", "subject"),
    ("body", "body"),
)
_MAX_TABLE_ROWS = 50


def _join(value: Any) -> Any:
    # Recipient lists read as one line in the preview.
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return ", ".join(value)
    return value


def _humanize(key: str) -> str:
    return key.replace("_", " ").strip().capitalize()


def _fields_from(values: dict, skip=("thought",)) -> list[dict]:
    return [
        {"key": _humanize(str(key)), "value": value}
        for key, value in values.items()
        if key not in skip
    ]


EMAIL_REPLY_TOOL_NAME = "reply_by_email"


def build_approval_preview(
    chat, tool, tool_name: str, args: Optional[dict]
) -> Optional[dict]:
    """
    :param chat: The chat the approval belongs to.
    :param tool: The `AgentTool` owning the call, or None for workspace tools.
    :param tool_name: The runtime tool name.
    :param args: The model's arguments.
    :return: `{kind: "email"|"fields"|"table", ...}` or None when nothing
        useful can be shown.
    """

    args = args if isinstance(args, dict) else {}
    try:
        if tool is not None and tool.service_id is not None:
            return _service_preview(chat, tool, args)
        if tool_name == EMAIL_REPLY_TOOL_NAME:
            return _email_reply_preview(chat, args)
        match = _ROW_TOOL_RE.match(tool_name)
        if match and match.group(1) in ("create", "update"):
            return _rows_preview(args.get("rows"))
        fields = _fields_from(args)
        return {"kind": "fields", "fields": fields} if fields else None
    except Exception:
        logger.exception("Failed to build the approval preview for {}", tool_name)
        fields = _fields_from(args)
        return {"kind": "fields", "fields": fields} if fields else None


def _email_reply_preview(chat, args: dict) -> Optional[dict]:
    from .channels.email import EmailAgentChatChannelType
    from .channels.registries import agent_chat_channel_type_registry

    channel = chat.channel
    if channel is None:
        return None
    channel_type = agent_chat_channel_type_registry.get(channel.type)
    if not isinstance(channel_type, EmailAgentChatChannelType):
        return None
    target = channel_type.reply_target(channel, chat)
    preview = {"kind": "email", "body": str(args.get("body") or "")}
    if target is not None:
        preview["to"] = target.to_address
        preview["subject"] = target.subject
    return preview


def _service_preview(chat, tool, args: dict) -> Optional[dict]:
    from baserow.core.services.handler import ServiceHandler  # noqa: F401

    service = tool.service.specific
    service_type = service.get_type()
    dispatch_context = AgentDispatchContext(chat=chat, runtime_inputs=args)
    resolved = service_type.resolve_service_formulas(service, dispatch_context)
    if service_type.type in _EMAIL_SERVICE_TYPES:
        email = {
            key: _join(resolved[source])
            for key, source in _EMAIL_FIELDS
            if source in resolved and resolved[source] not in (None, "", [])
        }
        if email:
            return {"kind": "email", **email}
    fields = _fields_from(resolved)
    return {"kind": "fields", "fields": fields} if fields else None


def _rows_preview(rows: Any) -> Optional[dict]:
    if not isinstance(rows, list) or not rows:
        return None
    rows = [row for row in rows if isinstance(row, dict)][:_MAX_TABLE_ROWS]
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(str(key))
    return {
        "kind": "table",
        "columns": columns,
        "rows": [[row.get(column) for column in columns] for row in rows],
    }
