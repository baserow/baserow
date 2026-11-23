from typing import Any

from baserow.core.prosemirror.utils import prosemirror_doc_to_plain_text


def row_comment_to_plain_text(message: dict[str, Any]) -> str:
    # prosemirror_doc_to_plain_text only reads a document's first block.
    return "\n".join(
        prosemirror_doc_to_plain_text({"type": "doc", "content": [block]})
        for block in message.get("content", [])
    )
