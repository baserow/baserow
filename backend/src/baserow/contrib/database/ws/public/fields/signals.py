from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.api.views.serializers import PublicFieldSerializer
from baserow.contrib.database.fields import signals as field_signals
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.registries import view_type_registry
from baserow.contrib.database.ws.fields.signals import RealtimeFieldMessages
from baserow.core.cache import local_cache
from baserow.core.db import specific_iterator
from baserow.ws.registries import page_registry


def _broadcast_payload_to_views_with_restricted_related_fields(
    payload: Dict[str, Any],
    serialized_related_fields: List[Dict[str, Any]],
    views_with_hidden_fields: List[Tuple[View, Set[int]]],
):
    view_page_type = page_registry.get("view")
    for view, hidden_fields in views_with_hidden_fields:
        payload["related_fields"] = [
            f for f in serialized_related_fields if f["id"] not in hidden_fields
        ]
        view_page_type.broadcast(
            payload,
            None,
            slug=view.slug,
        )


def _send_payload_to_public_views_where_field_not_hidden(
    field: Field, payload: Dict[str, Any]
):
    related_fields = payload.pop("related_fields", [])
    related_field_ids = [f["id"] for f in related_fields]

    views_with_hidden_fields = _get_views_where_field_visible_and_hidden_fields_in_view(
        field,
        hidden_fields_field_ids_filter=related_field_ids,
    )
    _broadcast_payload_to_views_with_restricted_related_fields(
        payload, related_fields, views_with_hidden_fields
    )


def _get_public_views_with_hidden_fields(
    table_id: int,
) -> List[Tuple[View, Set[int]]]:
    """
    Returns the public views for a table with their hidden field sets. Results
    are cached in the request-scoped local_cache so that repeated calls for the
    same table within a single request don't re-query.
    """

    def _fetch() -> List[Tuple[View, Set[int]]]:
        views_qs = (
            View.objects.filter(public=True, table_id=table_id)
            .select_related("table")
            .prefetch_related("table__field_set")
        )

        specific_views = specific_iterator(
            views_qs,
            per_content_type_queryset_hook=(
                lambda model, queryset: view_type_registry.get_by_model(
                    model
                ).enhance_queryset(queryset)
            ),
        )
        if not specific_views:
            return []

        table = specific_views[0].table
        all_field_ids = [f.id for f in table.field_set.all()]

        result = []
        for view in specific_views:
            view = view.specific
            view_type = view_type_registry.get_by_model(view)
            if not view_type.when_shared_publicly_requires_realtime_events:
                continue

            hidden_field_ids = view_type.get_hidden_fields(view, all_field_ids)
            result.append((view, hidden_field_ids))

        return result

    return local_cache.get(
        f"public_views_with_hidden_fields_{table_id}", default=_fetch
    )


def _get_views_where_field_visible_and_hidden_fields_in_view(
    field: Field,
    hidden_fields_field_ids_filter: Optional[Iterable[int]] = None,
) -> List[Tuple[View, Set[int]]]:
    """
    Finds all public views where field is visible, along with the set of hidden
    field ids in each view.

    :param field: The field to check visibility for.
    :param hidden_fields_field_ids_filter: When provided, restricts hidden field
        calculation to just these field ids plus the field itself.
    :return: A list of (view, hidden_field_ids) tuples for views where field is
        visible.
    """

    if hidden_fields_field_ids_filter is not None:
        restrict_to = {field.id, *hidden_fields_field_ids_filter}
        views_qs = (
            View.objects.filter(public=True, table_id=field.table_id)
            .select_related("table__database__workspace")
            .prefetch_related("table__field_set")
        )
        specific_views = specific_iterator(
            views_qs,
            per_content_type_queryset_hook=(
                lambda model, queryset: view_type_registry.get_by_model(
                    model
                ).enhance_queryset(queryset)
            ),
        )
        result = []
        for view in specific_views:
            view = view.specific
            view_type = view_type_registry.get_by_model(view)
            if not view_type.when_shared_publicly_requires_realtime_events:
                continue
            hidden_field_ids = view_type.get_hidden_fields(view, list(restrict_to))
            if field.id not in hidden_field_ids:
                result.append((view, hidden_field_ids))
        return result

    views_with_hidden = _get_public_views_with_hidden_fields(field.table_id)
    return [
        (view, hidden_field_ids)
        for view, hidden_field_ids in views_with_hidden
        if field.id not in hidden_field_ids
    ]


@receiver(field_signals.field_created)
def public_field_created(sender, field, related_fields, user, **kwargs):
    transaction.on_commit(
        lambda: _send_payload_to_public_views_where_field_not_hidden(
            field,
            RealtimeFieldMessages.field_created(
                field, related_fields, field_serializer_class=PublicFieldSerializer
            ),
        )
    )


@receiver(field_signals.field_restored)
def public_field_restored(sender, field, related_fields, user, **kwargs):
    transaction.on_commit(
        lambda: _send_payload_to_public_views_where_field_not_hidden(
            field,
            RealtimeFieldMessages.field_restored(
                field, related_fields, field_serializer_class=PublicFieldSerializer
            ),
        )
    )


@receiver(field_signals.field_updated)
def public_field_updated(sender, field, related_fields, user, **kwargs):
    transaction.on_commit(
        lambda: _send_payload_to_public_views_where_field_not_hidden(
            field,
            RealtimeFieldMessages.field_updated(
                field, related_fields, field_serializer_class=PublicFieldSerializer
            ),
        )
    )


@receiver(field_signals.before_field_deleted)
def public_before_field_deleted(sender, field_id, field, user, **kwargs):
    # We have to check where the field is visible before it is deleted.
    return _get_views_where_field_visible_and_hidden_fields_in_view(
        field,
        # We don't know yet which fields will be related_fields so calculate the
        # hidden_fields set for all fields in the view as any could potentially be
        # a related_field.
        hidden_fields_field_ids_filter=None,
    )


@receiver(field_signals.field_deleted)
def public_field_deleted(
    sender, field_id, field, related_fields, user, before_return, **kwargs
):
    def send_deleted():
        views = dict(before_return)[public_before_field_deleted]
        payload = RealtimeFieldMessages.field_deleted(
            PUBLIC_PLACEHOLDER_ENTITY_ID,
            field_id,
            related_fields,
            field_serializer_class=PublicFieldSerializer,
        )
        serialized_related_fields = payload.pop("related_fields", [])

        _broadcast_payload_to_views_with_restricted_related_fields(
            payload, serialized_related_fields, views
        )

    transaction.on_commit(send_deleted)
