from typing import Any, Dict, Optional

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.database.fields import signals as field_signals
from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.registries import view_type_registry
from baserow.contrib.database.ws.fields.signals import RealtimeFieldMessages
from baserow.core.db import specific_iterator
from baserow.ws.registries import page_registry
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType


def _broadcast_payload_to_all_restricted_views(
    user: AbstractUser,
    table_id: int,
    payload: Dict[str, Any],
    field_id: Optional[int] = None,
):
    base_qs = View.objects.filter(
        table_id=table_id,
        ownership_type=RestrictedViewOwnershipType.type,
    )

    if field_id is not None:
        # Batch-fetch all specific view subclasses in one query per type,
        # using enhance_queryset to prefetch field options so that
        # get_hidden_fields doesn't trigger N+1 queries.
        views = specific_iterator(
            base_qs.select_related("content_type").prefetch_related("table__field_set"),
            per_content_type_queryset_hook=(
                lambda model, queryset: view_type_registry.get_by_model(
                    model
                ).enhance_queryset(queryset)
            ),
        )
    else:
        views = base_qs

    view_page_type = page_registry.get("restricted_view")
    for view in views:
        if field_id is not None:
            view_type = view_type_registry.get_by_model(view)
            hidden_ids = view_type.get_hidden_fields(view)
            if field_id in hidden_ids:
                continue
        view_page_type.broadcast(
            payload,
            getattr(user, "web_socket_id", None),
            restricted_view_id=view.id,
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
            field_id=field.id,
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
            field_id=field.id,
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
            field_id=field.id,
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
            field_id=field_id,
        )
    )
