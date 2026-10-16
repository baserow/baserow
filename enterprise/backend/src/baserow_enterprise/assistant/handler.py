from contextlib import AbstractContextManager, aclosing, nullcontext
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Optional
from uuid import UUID, uuid4

from django.contrib.auth.models import AbstractUser
from django.db import DEFAULT_DB_ALIAS, transaction
from django.db.models import Count

from baserow.api.sessions import get_untrusted_client_session_id
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRun
from baserow.core.db import IsolationLevel, transaction_atomic
from baserow.core.models import Workspace

from .assistant import Assistant, assistant_message_payload
from .exceptions import AssistantChatDoesNotExist
from .model_profiles import ResolvedAssistantModelProfile
from .models import AssistantChat, AssistantChatMessage, AssistantChatPrediction
from .runs import ASSISTANT_RUN_TYPE
from .types import AiMessage, AssistantMessageUnion, HumanMessage, UIContext

PROVISIONAL_TITLE_LENGTH = 60


def _provisional_title(content: str) -> str:
    """
    :param content: The first message of a chat.
    :return: Its start on one line, shown in the chat list until the run
        generates a title.
    """

    return " ".join(content.split())[:PROVISIONAL_TITLE_LENGTH]


@dataclass(frozen=True)
class ChatSnapshot:
    """A chat's messages and its active run, read at one point in time."""

    messages: list[AssistantMessageUnion]
    active_run: Optional[ChatRun]
    latest_run: Optional[ChatRun]
    chat_title: str


def _snapshot_transaction() -> AbstractContextManager:
    """
    :return: A repeatable-read transaction on the primary, or nothing inside a
        caller's transaction, whose isolation can't change.
    """

    if transaction.get_connection(DEFAULT_DB_ALIAS).in_atomic_block:
        return nullcontext()
    return transaction_atomic(
        using=DEFAULT_DB_ALIAS, isolation_level=IsolationLevel.REPEATABLE_READ
    )


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

        chat, created = AssistantChat.objects.select_related(
            "workspace", "user__profile"
        ).get_or_create(
            uuid=chat_uid,
            defaults={"user": user, "workspace": workspace},
        )
        if chat.user_id != user.id or chat.workspace_id != workspace.id:
            raise AssistantChatDoesNotExist(
                f"Chat with UUID {chat_uid} does not exist in workspace {workspace.id}."
            )
        return chat, created

    def get_existing_chat(
        self,
        user: AbstractUser,
        workspace: Workspace,
        chat_uid: str | UUID,
    ) -> AssistantChat | None:
        """Return an existing chat only when it belongs to the requested workspace.

        A chat UUID is globally unique and supplied by the client. Treat a UUID owned
        by another user or workspace as missing so it can never be reused with a
        different workspace's permissions, model credentials, or tool context.

        :param user: The user requesting the chat.
        :param workspace: The workspace the request claims the chat belongs to.
        :param chat_uid: The unique identifier of the chat.
        :return: The matching chat, or ``None`` when the UUID is unused.
        :raises AssistantChatDoesNotExist: If the UUID belongs to another user or
            workspace.
        """

        try:
            chat = AssistantChat.objects.select_related(
                "workspace", "user__profile"
            ).get(uuid=chat_uid)
        except AssistantChat.DoesNotExist:
            return None
        if chat.user_id != user.id or chat.workspace_id != workspace.id:
            raise AssistantChatDoesNotExist(
                f"Chat with UUID {chat_uid} does not exist in workspace {workspace.id}."
            )
        return chat

    def list_chats(self, user: AbstractUser, workspace_id: int) -> list[AssistantChat]:
        """
        List all AI assistant chats for the user in the specified workspace.
        """

        return (
            AssistantChat.objects.filter(
                workspace_id=workspace_id,
                user=user,
            )
            .exclude(title="")
            .annotate(message_count=Count("messages"))
            .filter(message_count__gt=0)
            .order_by("-updated_on", "id")
        )

    def get_chat_message_by_id(self, user: AbstractUser, message_id: int) -> AiMessage:
        """
        Get a specific message from the AI assistant chat by its ID.

        :param user: The user requesting the message.
        :param message_id: The ID of the message to retrieve.
        :return: The AI assistant message.
        :raises AssistantChatDoesNotExist: If the chat or message does not exist.
        """

        try:
            return AssistantChatMessage.objects.select_related(
                "chat__workspace", "prediction"
            ).get(chat__user=user, id=message_id)
        except AssistantChatMessage.DoesNotExist:
            raise AssistantChatDoesNotExist(
                f"Message with ID {message_id} does not exist."
            )

    def list_chat_messages(self, chat: AssistantChat) -> list[AiMessage | HumanMessage]:
        """
        Get all messages from the AI assistant chat.

        :param chat: The AI assistant chat to get messages from.
        :return: A list of messages from the AI assistant chat.
        """

        return Assistant.list_chat_messages_for_chat(chat)

    def get_chat_snapshot(self, chat: AssistantChat) -> ChatSnapshot:
        """
        Reads the chat's messages and its active run in one repeatable-read
        transaction, so a run can't start or end unseen between the two reads.

        :param chat: The chat.
        :return: The messages, active run and latest run, from the same snapshot.
        """

        with _snapshot_transaction():
            chat_title = (
                AssistantChat.objects.using(DEFAULT_DB_ALIAS)
                .values_list("title", flat=True)
                .get(id=chat.id)
            )
            messages = self.list_chat_messages(chat)
            active_run = ChatRunHandler().get_active_run(ASSISTANT_RUN_TYPE, chat.id)
            latest_run = (
                ChatRun.objects.filter(run_type=ASSISTANT_RUN_TYPE, chat_id=chat.id)
                .order_by("-created_on", "-id")
                .first()
            )
        return ChatSnapshot(
            messages=messages,
            active_run=active_run,
            latest_run=latest_run,
            chat_title=chat_title,
        )

    def get_assistant(
        self,
        chat: AssistantChat,
        model_profile: ResolvedAssistantModelProfile | None = None,
    ) -> Assistant:
        """
        Get the assistant for the given chat.

        :param chat: The AI assistant chat to get the assistant for.
        :param model_profile: The model resolution already checked for this request.
        :return: The assistant for the given chat.
        """

        return Assistant(chat, model_profile=model_profile)

    def send_message(
        self,
        user: AbstractUser,
        workspace: Workspace,
        chat_uuid: str | UUID,
        content: str,
        ui_context: UIContext,
        tab_id: str,
    ) -> tuple[ChatRun, dict[str, Any]]:
        """
        Saves a human message and starts the background run that answers it, in
        one transaction, so a refused run leaves no message behind. A chat without
        a title gets a provisional one, which the run replaces.

        :param user: The user sending the message.
        :param workspace: The workspace of the chat.
        :param chat_uuid: The chat's client-generated uuid; a new uuid creates the
            chat.
        :param content: The message.
        :param ui_context: What the user was looking at when sending it.
        :param tab_id: The sending tab, the only one that follows Kuma's
            navigation.
        :return: The run, and the saved message as clients show it.
        """

        with transaction.atomic():
            chat, _ = self.get_or_create_chat(user, workspace, chat_uuid)
            generate_title = not chat.title
            if generate_title:
                chat.title = _provisional_title(content)
                chat.save(update_fields=["title", "updated_on"])
            human_message = AssistantChatMessage.objects.create(
                chat=chat, role=AssistantChatMessage.Role.HUMAN, content=content
            )
            serialized = assistant_message_payload(human_message)
            run = ChatRunHandler().start_run(
                ASSISTANT_RUN_TYPE,
                chat.id,
                workspace,
                user,
                {
                    "human_message_id": human_message.id,
                    "client_session_id": get_untrusted_client_session_id(user),
                    "action_group_id": str(uuid4()),
                    "ui_context": ui_context.model_dump(mode="json"),
                    "origin_tab_id": tab_id,
                    "generate_title": generate_title,
                },
                {"human_message": serialized},
            )
        return run, serialized

    def delete_predictions(
        self, older_than_days: int = 30, exclude_rated: bool = True
    ) -> tuple[int, dict]:
        """
        Delete predictions older than the specified number of days.

        :param older_than_days: The number of days to retain predictions.
        :param exclude_rated: Whether to exclude predictions that have been rated by
            users.
        :return: A tuple containing the number of deleted predictions and a dict with
            details.
        """

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        queryset = AssistantChatPrediction.objects.filter(created_on__lt=cutoff_date)

        if exclude_rated:
            queryset = queryset.filter(human_sentiment__isnull=True)

        return queryset.delete()

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
        :param ui_context: The UI context where the message was sent.
        :return: An async generator yielding messages from the assistant.
        """

        assistant = self.get_assistant(chat)
        message = HumanMessage(content=human_message, ui_context=ui_context)
        async with aclosing(assistant.astream_messages(message)) as messages:
            async for msg in messages:
                yield msg
