from functools import partial

from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.database.ws.fields.signals import RealtimeFieldMessages
from baserow.core import signals as core_signals
from baserow.core.ai_provider.signals import ai_provider_updated
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
    sender,
    model_availability_updated,
    provider_type=None,
    workspace=None,
    model_identifiers=None,
    **kwargs,
):
    """
    Re-serialize affected AI fields after provider availability changes.

    These are computed metadata changes, not schema changes, so this broadcasts
    directly instead of sending the database ``field_updated`` domain signal.
    Passing no excluded websocket ID ensures the admin's other open tabs update.
    A workspace-owned change cannot affect fields elsewhere, so only an
    instance-level change scans every workspace.
    """

    if not model_availability_updated:
        return

    fields = AIField.objects.filter(ai_generative_ai_type=provider_type).select_related(
        "table__database__workspace"
    )
    if workspace is not None:
        fields = fields.filter(table__database__workspace=workspace)
    if model_identifiers is not None:
        fields = fields.filter(ai_generative_ai_model__in=model_identifiers)

    _schedule_ai_field_error_broadcasts(fields)


@receiver(core_signals.workspace_updated)
def broadcast_workspace_ai_field_errors(
    sender, workspace, updated_fields=None, **kwargs
):
    if "generative_ai_models_settings" not in (updated_fields or []):
        return

    fields = AIField.objects.filter(
        table__database__workspace=workspace
    ).select_related("table__database__workspace")
    _schedule_ai_field_error_broadcasts(fields)
