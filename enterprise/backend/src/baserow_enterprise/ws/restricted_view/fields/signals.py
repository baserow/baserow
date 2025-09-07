from typing import Any, Dict

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.database.fields import signals as field_signals
from baserow.contrib.database.views.models import View
from baserow.contrib.database.ws.fields.signals import RealtimeFieldMessages
from baserow.ws.registries import page_registry
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType


def _broadcast_payload_to_all_restricted_views(
    user: AbstractUser,
    table_id: int,
    payload: Dict[str, Any],
):
    views = View.objects.filter(
        table_id=table_id,
        ownership_type=RestrictedViewOwnershipType.type,
    ).values_list("id", flat=True)

    view_page_type = page_registry.get("restricted_view")
    for view_id in views:
        view_page_type.broadcast(
            payload,
            getattr(user, "web_socket_id", None),
            restricted_view_id=view_id,
        )


@receiver(field_signals.field_created)
def field_created(sender, field, related_fields, user, **kwargs):
    transaction.on_commit(
        lambda: _broadcast_payload_to_all_restricted_views(
            user,
            field.table_id,
            RealtimeFieldMessages.field_created(
                field,
                related_fields,
            ),
        )
    )


@receiver(field_signals.field_restored)
def field_restored(sender, field, related_fields, user, **kwargs):
    transaction.on_commit(
        lambda: _broadcast_payload_to_all_restricted_views(
            user,
            field.table_id,
            RealtimeFieldMessages.field_restored(
                field,
                related_fields,
            ),
        )
    )


@receiver(field_signals.field_updated)
def field_updated(sender, field, related_fields, user, **kwargs):
    transaction.on_commit(
        lambda: _broadcast_payload_to_all_restricted_views(
            user,
            field.table_id,
            RealtimeFieldMessages.field_updated(
                field,
                related_fields,
            ),
        )
    )


@receiver(field_signals.field_deleted)
def field_deleted(
    sender, field_id, field, related_fields, user, before_return, **kwargs
):
    transaction.on_commit(
        lambda: _broadcast_payload_to_all_restricted_views(
            user,
            field.table_id,
            RealtimeFieldMessages.field_deleted(
                field.table_id,
                field_id,
                related_fields,
            ),
        )
    )
