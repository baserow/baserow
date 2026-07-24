from functools import partial

from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.database.table.signals import table_schema_changed
from baserow.contrib.database.ws.fields.signals import RealtimeFieldMessages
from baserow.core import signals as core_signals
from baserow.core.ai_provider.signals import ai_provider_availability_changed
from baserow.core.cache import local_cache
from baserow.ws.registries import page_registry

from .models import AIField


@receiver(table_schema_changed)
def invalidate_ai_prompt_field_ids_cache(sender, table_id, **kwargs):
    # Invalidate the cached field ids used by AI prompt validation (see
    # visitors.get_table_field_ids) when a field is added/updated/trashed/restored.
    local_cache.delete(f"ai_prompt_table_field_ids_{table_id}")


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


@receiver(ai_provider_availability_changed)
def broadcast_ai_field_errors(sender, provider_type, model_identifiers=None, **kwargs):
    """
    Re-serialize affected AI fields after provider availability changes.

    These are computed metadata changes, not schema changes, so this broadcasts
    directly instead of sending the database ``field_updated`` domain signal.
    Passing no excluded websocket ID ensures the admin's other open tabs update.
    """

    fields = AIField.objects.filter(ai_generative_ai_type=provider_type).select_related(
        "table__database__workspace"
    )
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
