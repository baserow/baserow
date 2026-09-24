from functools import partial
from typing import Any

from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.database.ws.fields.signals import RealtimeFieldMessages
from baserow.core.ai_provider.signals import ai_provider_updated
from baserow.core.models import Workspace
from baserow.ws.registries import page_registry

from .models import AIField


def _broadcast_ai_field_errors(field, related_fields):
    table_page_type = page_registry.get("table")
    table_page_type.broadcast(
        RealtimeFieldMessages.field_updated(field, related_fields),
        None,
        table_id=field.table_id,
    )


def _schedule_ai_field_error_broadcasts(fields):
    fields_by_table = {}
    for field in fields:
        fields_by_table.setdefault(field.table_id, []).append(field)

    for table_fields in fields_by_table.values():
        transaction.on_commit(
            partial(
                _broadcast_ai_field_errors,
                table_fields[0],
                table_fields[1:],
            )
        )


@receiver(ai_provider_updated)
def broadcast_ai_field_errors(
    sender: type,
    model_availability_updated: bool,
    provider_type: str | None = None,
    workspace: Workspace | None = None,
    model_identifiers: set[str] | None = None,
    **kwargs: Any,
) -> None:
    """
    Re-serialize affected AI fields after provider availability changes.

    These are computed metadata changes, not schema changes, so this broadcasts
    directly instead of sending the database ``field_updated`` domain signal.
    Passing no excluded websocket ID ensures the admin's other open tabs update.
    Instance-level changes are not broadcast: open tables pick them up on reload.

    :param sender: The service class that sent the signal.
    :param model_availability_updated: Whether the change can alter which models
        are available; nothing is broadcast when it cannot.
    :param provider_type: The provider type whose AI fields may be affected.
    :param workspace: The workspace whose providers changed, or None for the
        instance scope.
    :param model_identifiers: The affected models, or None for every model of
        ``provider_type``.
    :param kwargs: The remaining signal arguments, which this receiver ignores.
    """

    if not model_availability_updated or workspace is None or provider_type is None:
        return

    fields = AIField.objects.filter(
        ai_generative_ai_type=provider_type,
        table__database__workspace=workspace,
    ).select_related("table__database__workspace")
    if model_identifiers is not None:
        fields = fields.filter(ai_generative_ai_model__in=model_identifiers)

    _schedule_ai_field_error_broadcasts(fields)
