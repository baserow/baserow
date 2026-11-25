from typing import Any

import jwt

from baserow.contrib.agent.models import AgentConversation
from baserow.core.public_sharing import (
    decode_public_access_token,
    encode_public_access_token,
)
from baserow_enterprise.agent.constants import PUBLIC_CHAT_CONVERSATION_CLAIM
from baserow_enterprise.agent.models import PublicChatAgentChannel


def encode_access_token(chat: PublicChatAgentChannel) -> str:
    """
    :param chat: The public chat whose password the visitor gave.
    :return: A token proving the visitor knows the chat's current password.
    """

    return encode_public_access_token(chat.slug, chat.password)


def encode_conversation_token(
    chat: PublicChatAgentChannel, conversation: AgentConversation
) -> str:
    """
    Signed with the password's hash, so it also proves the password, and a changed
    password ends every open conversation.

    :param chat: The public chat the conversation was started through.
    :param conversation: The visitor's conversation.
    :return: A token that opens the conversation to whoever holds it.
    """

    return encode_public_access_token(
        chat.slug,
        chat.password,
        {PUBLIC_CHAT_CONVERSATION_CLAIM: str(conversation.uuid)},
    )


def decode_token(
    chat: PublicChatAgentChannel, token: str | None
) -> dict[str, Any] | None:
    """
    :param chat: The public chat the request is for.
    :param token: The token the request carries, if any.
    :return: The token's payload, or None when the token is missing or wasn't
        issued for this chat's current link and password.
    """

    if token is None:
        return None
    try:
        return decode_public_access_token(chat.slug, chat.password, token)
    except jwt.InvalidTokenError:
        return None
