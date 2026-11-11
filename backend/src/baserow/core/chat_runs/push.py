import asyncio

from django.db import transaction

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from loguru import logger

from .constants import PUSH_TIMEOUT_SECONDS
from .models import ChatRun

CHAT_RUN_CHANGED_MESSAGE_TYPE = "chat_run_changed"


def chat_group_name(run_type: str, chat_id: int) -> str:
    return f"chat-runs-{run_type}-{chat_id}"


async def notify_run(run: ChatRun) -> None:
    """Discovery only. Output and replay never enter the channel layer."""

    try:
        async with asyncio.timeout(PUSH_TIMEOUT_SECONDS):
            await get_channel_layer().group_send(
                chat_group_name(run.run_type, run.chat_id),
                {
                    "type": "broadcast_to_group",
                    "payload": {
                        "type": CHAT_RUN_CHANGED_MESSAGE_TYPE,
                        "run_id": str(run.id),
                        "run_type": run.run_type,
                        "chat_id": run.chat_id,
                        "status": str(run.status),
                    },
                    "ignore_web_socket_id": None,
                },
            )
    except Exception as exc:
        logger.warning(
            "Could not announce chat run {} ({})", run.id, type(exc).__name__
        )


def notify_run_on_commit(run: ChatRun) -> None:
    transaction.on_commit(lambda: async_to_sync(notify_run)(run), robust=True)
