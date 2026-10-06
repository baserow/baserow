from django.contrib.contenttypes.models import ContentType
from django.dispatch import receiver

from baserow.core.signals import application_deleted

from .models import AgentApplication, AgentChat


@receiver(application_deleted)
def cancel_runs_of_trashed_agent(sender, application, user=None, **kwargs):
    """
    Trashing an agent must stop what it is doing: running conversations are
    cancelled the same way a user cancels them, so the worker stops at the
    next step. Paused approvals stay pending in case the agent is restored.
    """

    from .handler import AgentChatHandler

    # Every application type passes through here; the content type check
    # avoids loading the specific instance for the others.
    if (
        application.content_type_id
        != ContentType.objects.get_for_model(AgentApplication).id
    ):
        return

    handler = AgentChatHandler()
    running = AgentChat.objects.filter(
        agent__application_id=application.id,
        status=AgentChat.Status.IN_PROGRESS,
    ).select_related("agent__application")
    for chat in running:
        handler.cancel_chat_run(chat, user)
