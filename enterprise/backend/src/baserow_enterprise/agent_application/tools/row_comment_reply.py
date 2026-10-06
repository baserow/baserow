from typing import Annotated

from asgiref.sync import sync_to_async
from pydantic import Field
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from ..deps import AgentRunDeps


async def reply_to_row_comment(
    ctx: RunContext[AgentRunDeps],
    message: Annotated[
        str,
        Field(description="The reply, as plain text. Keep it short and direct."),
    ],
) -> dict:
    """
    Posts your answer as a comment on the row this conversation started from,
    so the person who commented reads it where they asked. Use it for the
    final answer; the conversation itself is only visible inside the agent.
    """

    payload = ctx.deps.chat.event_payload or {}
    table_id, row_id = payload.get("table_id"), payload.get("row_id")
    if not table_id or not row_id:
        return {"error": "This conversation was not started by a row comment."}

    def post():
        from baserow.core.prosemirror.utils import prosemirror_doc_from_plain_text
        from baserow_premium.row_comments.handler import RowCommentHandler

        comment = RowCommentHandler.create_application_comment(
            ctx.deps.agent.application,
            table_id,
            row_id,
            prosemirror_doc_from_plain_text(message),
        )
        return {"success": True, "comment_id": comment.id}

    try:
        return await sync_to_async(post)()
    except Exception as exc:  # noqa: BLE001
        return {"error": f"The comment could not be posted: {exc}"}


def build_row_comment_reply_toolset() -> FunctionToolset:
    return FunctionToolset([reply_to_row_comment], max_retries=2)
