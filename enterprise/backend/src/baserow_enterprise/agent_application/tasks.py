import asyncio
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from loguru import logger

from baserow.config.celery import app


def _execute_agent_chat_turn(chat_id: int, prompt_message_id: int | None):
    """
    Executes one turn of an agent chat, either started by a prompt message or
    resumed from the approval queue (no prompt message).
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
    ).get(id=chat_id)
    prompt_message = (
        chat.messages.get(id=prompt_message_id)
        if prompt_message_id is not None
        else None
    )

    chat.status = AgentChat.Status.IN_PROGRESS
    chat.started_on = timezone.now()
    chat.completed_on = None
    chat.error = ""
    chat.save(update_fields=["status", "started_on", "completed_on", "error"])
    broadcast_chat_updated(chat)

    runner = None
    try:
        runner = AgentRunner(chat)
        if prompt_message is not None:
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
        if text:
            channel_type.send_response(channel, chat, text)
    except Exception:
        logger.exception("Failed to notify chat channel for chat {}", chat.id)


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


@app.task(bind=True, queue="export")
def process_agent_channel_message(
    self, channel_id: int, session_key: str, text: str, sender_name: str = ""
):
    """
    Handles a message received through an external chat channel (e.g. a
    Slack DM): finds or creates the chat for that external conversation and
    starts a run. The webhook view only verifies and enqueues, because the
    external service expects an immediate response.
    """

    from .channels.registries import start_channel_chat
    from .models import AgentChatChannel

    channel = (
        AgentChatChannel.objects.select_related("application__workspace")
        .filter(id=channel_id)
        .first()
    )
    if channel is None:
        return

    start_channel_chat(channel, session_key, text, sender_name)


@app.task(bind=True, queue="export")
def clean_up_old_agent_chats(self):
    """
    Deletes automatically started (trigger/setup) chats past the retention
    limits, and recovers chats whose run died without finalizing (e.g. a
    killed worker), which would otherwise stay "running" forever and block
    new messages. Manual conversations are only deleted by users.
    """

    from .models import AgentChat
    from .realtime import broadcast_chat_updated

    stuck_cutoff = timezone.now() - timedelta(
        minutes=settings.AGENT_APPLICATION_CHAT_STUCK_TIMEOUT_MINUTES
    )
    stuck_chats = AgentChat.objects.filter(
        status__in=[AgentChat.Status.IN_PROGRESS, AgentChat.Status.CANCELING],
        updated_on__lt=stuck_cutoff,
    ).select_related("agent")
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

    automated_chats.filter(updated_on__lt=cutoff).delete()

    max_entries = settings.AGENT_APPLICATION_CHAT_HISTORY_MAX_ENTRIES
    agent_ids = automated_chats.values_list("agent_id", flat=True).order_by().distinct()
    for agent_id in agent_ids:
        ids_to_keep = automated_chats.filter(agent_id=agent_id).order_by("-updated_on")[
            :max_entries
        ]
        automated_chats.filter(agent_id=agent_id).exclude(id__in=ids_to_keep).delete()


@app.on_after_finalize.connect
def setup_periodic_agent_application_tasks(sender, **kwargs):
    from django.conf import settings

    sender.add_periodic_task(
        timedelta(minutes=settings.AGENT_APPLICATION_CHAT_CLEANUP_INTERVAL_MINUTES),
        clean_up_old_agent_chats.s(),
        name="agent-application-chat-cleanup",
    )
