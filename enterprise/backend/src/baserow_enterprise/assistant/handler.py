from typing import AsyncGenerator
from uuid import UUID

from django.contrib.auth.models import AbstractUser

from baserow.core.models import Workspace

from .assistant import Assistant
from .exceptions import AssistantChatDoesNotExist
from .models import AssistantChat
from .types import AiMessage, AssistantMessageUnion, HumanMessage, UIContext


class AssistantHandler:
    def get_chat(self, user: AbstractUser, chat_uid: str | UUID) -> AssistantChat:
        """
        Get the AI assistant chat for the user with the given chat UID.

        :param user: The user requesting the chat.
        :param chat_uid: The unique identifier of the chat.
        :return: The AI assistant chat for the user.
        :raises AssistantChatDoesNotExist: If the chat does not exist.
        """

        try:
            return AssistantChat.objects.select_related(
                "workspace", "user__profile"
            ).get(user=user, uuid=chat_uid)
        except AssistantChat.DoesNotExist:
            raise AssistantChatDoesNotExist(
                f"Chat with UUID {chat_uid} does not exist."
            )

    def get_or_create_chat(
        self,
        user: AbstractUser,
        workspace: Workspace,
        chat_uid: str | UUID,
    ) -> tuple[AssistantChat, bool]:
        """
        Get or create an AI assistant chat for the user in the specified workspace.

        :param user: The user requesting the chat.
        :param workspace: The workspace in which to create the chat.
        :param chat_uid: The unique identifier of the chat.
        :return: A tuple containing the AI assistant chat and a boolean indicating
            whether it was created.
        """

        try:
            chat = self.get_chat(user, chat_uid)
            created = False
        except AssistantChatDoesNotExist:
            chat = AssistantChat.objects.create(
                uuid=chat_uid, user=user, workspace=workspace
            )
            created = True
        return chat, created

    def list_chats(self, user: AbstractUser, workspace_id: int) -> list[AssistantChat]:
        """
        List all AI assistant chats for the user in the specified workspace.
        """

        return AssistantChat.objects.filter(
            workspace_id=workspace_id, user=user
        ).order_by("-updated_on", "id")

    def list_chat_messages(self, chat: AssistantChat) -> list[AiMessage | HumanMessage]:
        """
        Get all messages from the AI assistant chat.

        :param chat: The AI assistant chat to get messages from.
        :return: A list of messages from the AI assistant chat.
        """

        assistant = self.get_assistant(chat)
        return assistant.list_chat_messages()

    def get_assistant(self, chat: AssistantChat) -> Assistant:
        """
        Get the assistant for the given chat.

        :param chat: The AI assistant chat to get the assistant for.
        :return: The assistant for the given chat.
        """

        return Assistant(chat)

    async def astream_assistant_messages(
        self,
        chat: AssistantChat,
        human_message: str,
        ui_context: UIContext | None = None,
    ) -> AsyncGenerator[AssistantMessageUnion, None]:
        """
        Stream messages from the assistant for the given chat and new message.

        :param chat: The AI assistant chat to get the assistant for.
        :param human_message: The new message from the user.
        :param ui_ontext: The UI context where the message was sent.
        :return: An async generator yielding messages from the assistant.
        """

        assistant = self.get_assistant(chat)
        async for message in assistant.astream_messages(
            human_message, ui_context=ui_context
        ):
            yield message
