from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from oauth2_provider.models import get_access_token_model, get_application_model

from baserow.config.celery import app
from baserow.core.mcp.models import MCPEndpoint


@app.task(bind=True, queue="export")
def delete_unused_mcp_oauth_clients(self):
    """
    Deletes clients that registered themselves through DCR but never got a grant,
    so anonymous registrations can't pile up.
    """

    Application = get_application_model()
    cutoff = timezone.now() - timedelta(days=settings.MCP_OAUTH_UNUSED_DCR_CLIENT_DAYS)
    # Includes grants in trashed workspaces, which can still be restored.
    grants = MCPEndpoint.objects_and_trash.filter(oauth_client_id=OuterRef("client_id"))
    unused = Application.objects.filter(
        registration_source=Application.RegistrationSource.DCR,
        created__lt=cutoff,
    ).exclude(Exists(grants))
    with transaction.atomic():
        # The registration tokens go first: the token models reference each other,
        # so the cascade from the application deletes them after it.
        get_access_token_model().objects.filter(application__in=unused).delete()
        unused.delete()


@app.on_after_finalize.connect
def setup_periodic_mcp_oauth_tasks(sender, **kwargs):
    sender.add_periodic_task(timedelta(hours=6), delete_unused_mcp_oauth_clients.s())
