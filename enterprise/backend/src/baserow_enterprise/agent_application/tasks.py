import asyncio
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from loguru import logger

from baserow.config.celery import app


def _execute_agent_chat_turn(
    chat_id: int, prompt_message_id: int | None, inline: bool = False
):
    """
    Executes one turn of an agent chat, either started by a prompt message or
    resumed from the approval queue (no prompt message).

    :param inline: The turn runs inside a caller that may hold a transaction
        (a "Run agent" service waiting for the answer). The runner's database
        work then goes through the caller's own connection, where the chat it
        just created is visible, instead of the separate thread `asyncio.run`
        would use.
    """

    from .chat_types import AiErrorMessage
    from .exceptions import AgentChatRunCancelled
    from .models import AgentChat
    from .realtime import broadcast_chat_event, broadcast_chat_updated
    from .runner import AgentRunner

    chat = AgentChat.objects.select_related(
        "agent__application__workspace",
        "agent__application__agent_identity",
        "user",
        # The runner broadcasts from async code, where the channel can no
        # longer be lazily loaded (public web chat filtering needs it).
        "channel",
    ).get(id=chat_id)
    application = chat.agent.application
    if application.trashed or application.workspace.trashed:
        # Queued or resumed after the agent was trashed: nothing runs for a
        # trashed agent, and the chat is left idle for a possible restore.
        if chat.status != AgentChat.Status.AWAITING_APPROVAL:
            chat.status = AgentChat.Status.IDLE
            chat.save(update_fields=["status", "updated_on"])
            broadcast_chat_updated(chat)
        return
    prompt_message = (
        chat.messages.get(id=prompt_message_id)
        if prompt_message_id is not None
        else None
    )

    chat.status = AgentChat.Status.IN_PROGRESS
    chat.started_on = timezone.now()
    chat.completed_on = None
    chat.error = ""
    chat.save(
        update_fields=["status", "started_on", "completed_on", "error", "updated_on"]
    )
    broadcast_chat_updated(chat)

    runner = None
    try:
        runner = AgentRunner(chat)
        if inline:
            from asgiref.sync import async_to_sync

            if prompt_message is not None:
                async_to_sync(runner.arun)(prompt_message)
            else:
                async_to_sync(runner.arun_resume)()
        elif prompt_message is not None:
            asyncio.run(runner.arun(prompt_message))
        else:
            asyncio.run(runner.arun_resume())
        if runner.paused_for_approval:
            chat.status = AgentChat.Status.AWAITING_APPROVAL
        else:
            chat.status = AgentChat.Status.IDLE
    except AgentChatRunCancelled:
        chat.status = AgentChat.Status.IDLE
    except Exception as exc:
        logger.exception("Agent chat {} run failed", chat_id)
        chat.status = AgentChat.Status.ERROR
        chat.error = str(exc)[:5000]
        if runner is None:
            # The runner broadcasts its own errors; failures before it could
            # be constructed (e.g. no model configured) must still reach
            # watching browsers.
            broadcast_chat_event(chat, AiErrorMessage(content=str(exc)).model_dump())
    finally:
        chat.completed_on = timezone.now()
        chat.save(update_fields=["status", "completed_on", "error", "updated_on"])
        broadcast_chat_updated(chat)
        _notify_chat_channel(chat)


def _notify_chat_channel(chat):
    """
    Posts the outcome of a finished run back to the external chat channel the
    conversation came from (e.g. the Slack thread).
    """

    from .channels.registries import agent_chat_channel_type_registry
    from .models import AgentChat, AgentChatMessage

    if chat.channel_id is None or chat.status in (
        AgentChat.Status.IN_PROGRESS,
        AgentChat.Status.CANCELING,
    ):
        return

    try:
        channel = chat.channel
        channel_type = agent_chat_channel_type_registry.get(channel.type)
        if chat.status == AgentChat.Status.ERROR:
            text = "Something went wrong while running the agent."
        elif chat.status == AgentChat.Status.AWAITING_APPROVAL:
            text = (
                "The agent wants to make changes that require approval. "
                "Please review them in Baserow."
            )
        else:
            last_ai_message = (
                chat.messages.filter(role=AgentChatMessage.Role.AI)
                .order_by("-id")
                .first()
            )
            text = (last_ai_message and last_ai_message.content) or ""
        channel_type.deliver_outcome(channel, chat, chat.status, text)
    except Exception:
        logger.exception("Failed to notify chat channel for chat {}", chat.id)


def execute_chat_turn_inline(chat_id: int, prompt_message_id: int) -> None:
    """
    Runs a turn in the calling process. For a sub agent the parent's run is
    already a worker thread waiting on the tool, so the queue would only add
    a hop; the turn runs in that thread instead.
    """

    _execute_agent_chat_turn(chat_id, prompt_message_id, inline=True)


@app.task(bind=True, queue="export")
def run_agent_chat(self, chat_id: int, prompt_message_id: int):
    """
    Executes one turn of an agent chat. Runs on the export queue because agent
    runs are long-running LLM tasks.
    """

    _execute_agent_chat_turn(chat_id, prompt_message_id)


@app.task(bind=True, queue="export")
def resume_agent_chat(self, chat_id: int):
    """
    Resumes an agent chat that paused on tool calls awaiting approval, after
    every pending approval has been decided.
    """

    _execute_agent_chat_turn(chat_id, None)


# A message that arrives while the agent is still answering the previous one
# in the same thread is retried for a couple of minutes instead of dropped.
CHANNEL_MESSAGE_RETRY_SECONDS = 5
CHANNEL_MESSAGE_MAX_RETRIES = 24


@app.task(bind=True, queue="export", max_retries=CHANNEL_MESSAGE_MAX_RETRIES)
def process_agent_channel_message(
    self,
    channel_id: int,
    session_key: str,
    text: str,
    sender_name: str = "",
    attachments: list | None = None,
    title: str = "",
):
    """
    Handles a message received through an external chat channel (e.g. a
    Slack thread): finds or creates the chat for that external conversation
    and starts a run. The webhook view only verifies and enqueues, because
    the external service expects an immediate response.
    """

    from .channels.registries import (
        agent_chat_channel_type_registry,
        start_channel_chat,
    )
    from .exceptions import AgentChatAlreadyRunning
    from .models import AgentChat, AgentChatChannel

    channel = (
        AgentChatChannel.objects.select_related("application__workspace")
        .filter(
            id=channel_id,
            application__trashed=False,
            application__workspace__trashed=False,
        )
        .first()
    )
    if channel is None:
        return

    try:
        start_channel_chat(
            channel,
            session_key,
            text,
            sender_name,
            attachments=attachments,
            title=title,
        )
    except AgentChatAlreadyRunning:
        if self.request.retries < CHANNEL_MESSAGE_MAX_RETRIES:
            raise self.retry(countdown=CHANNEL_MESSAGE_RETRY_SECONDS)
        chat = AgentChat.objects.filter(
            channel=channel, channel_session_key=session_key
        ).first()
        if chat is not None:
            agent_chat_channel_type_registry.get(channel.type).send_response(
                channel,
                chat,
                "The agent is still busy with the previous message; please "
                "try again once it has answered.",
            )


@app.task(bind=True, queue="export")
def clean_up_old_agent_chats(self):
    """
    Deletes automatically started (trigger/setup) chats past the retention
    limits, and recovers chats whose run died without finalizing (e.g. a
    killed worker), which would otherwise stay "running" forever and block
    new messages. Manual conversations are only deleted by users.
    """

    from .handler import AgentChatHandler
    from .models import AgentChat
    from .realtime import broadcast_chat_updated

    stuck_cutoff = timezone.now() - timedelta(
        minutes=settings.AGENT_APPLICATION_CHAT_STUCK_TIMEOUT_MINUTES
    )
    stuck_chats = (
        AgentChat.objects.filter(
            status__in=[AgentChat.Status.IN_PROGRESS, AgentChat.Status.CANCELING],
            updated_on__lt=stuck_cutoff,
        )
        .defer("message_history")
        .select_related("agent")
    )
    for chat in stuck_chats:
        chat.status = AgentChat.Status.ERROR
        chat.error = "The run did not finish and has been marked as failed."
        chat.completed_on = timezone.now()
        chat.save(update_fields=["status", "error", "completed_on", "updated_on"])
        broadcast_chat_updated(chat)

    cutoff = timezone.now() - timedelta(
        days=settings.AGENT_APPLICATION_CHAT_HISTORY_MAX_DAYS
    )
    automated_chats = AgentChat.objects.exclude(source=AgentChat.Source.MANUAL).exclude(
        status__in=[AgentChat.Status.IN_PROGRESS, AgentChat.Status.CANCELING]
    )

    # Deleted one by one through the handler so open conversation lists and
    # approval counters learn about it, like a deletion by a user.
    def delete_chats(queryset):
        # The history can be megabytes per chat and is of no use to a delete.
        for chat in queryset.defer("message_history").select_related(
            "agent__application"
        ):
            AgentChatHandler().delete_chat(chat)

    delete_chats(automated_chats.filter(updated_on__lt=cutoff))

    max_entries = settings.AGENT_APPLICATION_CHAT_HISTORY_MAX_ENTRIES
    agent_ids = automated_chats.values_list("agent_id", flat=True).order_by().distinct()
    for agent_id in agent_ids:
        ids_to_keep = automated_chats.filter(agent_id=agent_id).order_by("-updated_on")[
            :max_entries
        ]
        delete_chats(
            automated_chats.filter(agent_id=agent_id).exclude(id__in=ids_to_keep)
        )


@app.task(bind=True, queue="export")
def poll_agent_mailbox_channels(self):
    """
    Fetches new mail for every enabled Gmail and Outlook channel. Each
    channel is polled under its own lock, so a slow mailbox never holds up
    the others and an overlapping beat tick skips it.
    """

    from .channels.mailbox import poll_mailbox_channels

    poll_mailbox_channels()


@app.on_after_finalize.connect
def setup_periodic_agent_application_tasks(sender, **kwargs):
    from django.conf import settings

    sender.add_periodic_task(
        timedelta(minutes=settings.AGENT_APPLICATION_CHAT_CLEANUP_INTERVAL_MINUTES),
        clean_up_old_agent_chats.s(),
        name="agent-application-chat-cleanup",
    )
    sender.add_periodic_task(
        timedelta(seconds=settings.AGENT_APPLICATION_MAILBOX_POLL_INTERVAL_SECONDS),
        poll_agent_mailbox_channels.s(),
        name="agent-application-mailbox-poll",
    )
