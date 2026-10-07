from typing import Annotated

from asgiref.sync import sync_to_async
from pydantic import Field
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from ..deps import AgentRunDeps


async def reply_by_email(
    ctx: RunContext[AgentRunDeps],
    body: Annotated[
        str,
        Field(
            description=(
                "The reply, as plain text the way an email reads: a greeting, "
                "the answer, a sign-off. No markdown."
            )
        ),
    ],
) -> dict:
    """
    Sends your reply by email to the person this conversation is with, in
    the same email thread. This is the only way they receive an answer.
    """

    def post():
        from ..channels.email import EmailAgentChatChannelType, EmailReplyNotPossible
        from ..channels.registries import agent_chat_channel_type_registry

        chat = ctx.deps.chat
        channel = chat.channel
        channel_type = (
            agent_chat_channel_type_registry.get(channel.type) if channel else None
        )
        if not isinstance(channel_type, EmailAgentChatChannelType):
            return {"error": "This conversation did not come in by email."}
        try:
            sent = channel_type.reply(channel, chat, body)
        except EmailReplyNotPossible as exc:
            return {"error": str(exc)}
        return {"sent": True, **sent}

    try:
        return await sync_to_async(post)()
    except Exception as exc:  # noqa: BLE001
        return {"error": f"The email could not be sent: {exc}"}


def build_email_reply_toolset() -> FunctionToolset:
    return FunctionToolset([reply_by_email], max_retries=2)
