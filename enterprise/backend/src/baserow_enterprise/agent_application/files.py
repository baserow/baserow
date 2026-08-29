"""
Loads user files into agent run prompts. Files come from two places: message
attachments a user dropped into the conversation, and file field values found
in the event payload of a triggered run (row created/updated).
"""

from typing import Any

from loguru import logger
from pydantic_ai.messages import BinaryContent

from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.user_files.models import UserFile

MAX_PROMPT_FILES = 10
MAX_PROMPT_FILE_SIZE = 15 * 1024 * 1024  # per file, in bytes
# Decoded text file content is inlined into the prompt instead of being sent
# as binary, which every provider supports.
MAX_TEXT_FILE_CHARS = 50000
TEXT_MIME_TYPES = {
    "application/json",
    "application/xml",
    "application/x-yaml",
    "application/csv",
}


def _is_user_file_dict(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("name"), str)
        and "visible_name" in value
    )


def extract_payload_files(payload: Any, found: list[dict] | None = None) -> list[dict]:
    """
    Recursively collects file field values (serialized user file dicts) from
    a trigger event payload, so files attached to a created/updated row can
    be injected into the run.
    """

    if found is None:
        found = []

    if _is_user_file_dict(payload):
        found.append(payload)
    elif isinstance(payload, dict):
        for value in payload.values():
            extract_payload_files(value, found)
    elif isinstance(payload, list):
        for value in payload:
            extract_payload_files(value, found)

    return found


def _load_user_file_part(user_file: UserFile, visible_name: str) -> Any | None:
    if user_file.size > MAX_PROMPT_FILE_SIZE:
        return (
            f"[The attached file '{visible_name}' was skipped because it is "
            f"larger than {MAX_PROMPT_FILE_SIZE // (1024 * 1024)}MB.]"
        )

    storage = get_default_storage()
    path = UserFileHandler().user_file_path(user_file.name)
    with storage.open(path, "rb") as handle:
        data = handle.read(MAX_PROMPT_FILE_SIZE)

    mime_type = user_file.mime_type or "application/octet-stream"
    if mime_type.startswith("text/") or mime_type in TEXT_MIME_TYPES:
        text = data.decode("utf-8", errors="replace")
        if len(text) > MAX_TEXT_FILE_CHARS:
            text = text[:MAX_TEXT_FILE_CHARS] + "… (truncated)"
        return f"Content of the attached file '{visible_name}':\n{text}"

    return BinaryContent(data=data, media_type=mime_type)


def load_prompt_file_parts(file_dicts: list[dict]) -> list[Any]:
    """
    Turns serialized user file dicts into prompt parts: text files are
    inlined as text, everything else becomes binary content the model
    provider receives directly (images, PDFs, ...).
    """

    parts = []
    seen_names = set()

    for file_dict in file_dicts:
        if len(parts) >= MAX_PROMPT_FILES:
            parts.append(
                f"[Only the first {MAX_PROMPT_FILES} attached files were "
                "included; the rest were skipped.]"
            )
            break

        name = file_dict.get("name")
        if not isinstance(name, str) or name in seen_names:
            continue
        seen_names.add(name)

        try:
            user_file = UserFile.objects.all().name(name).first()
        except Exception:
            # Trigger payloads can contain anything shaped like a file dict;
            # a malformed name is simply not a file.
            continue
        if user_file is None:
            continue

        visible_name = file_dict.get("visible_name") or user_file.original_name
        try:
            part = _load_user_file_part(user_file, visible_name)
        except Exception:
            logger.exception("Failed to load prompt file {}", name)
            part = f"[The attached file '{visible_name}' could not be loaded.]"

        if part is not None:
            parts.append(part)

    return parts
