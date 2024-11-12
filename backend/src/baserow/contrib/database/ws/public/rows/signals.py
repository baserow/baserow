from typing import Any, Dict, List, Optional

from django.db import transaction
from django.dispatch import receiver

from opentelemetry import trace

from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.api.rows.serializers import serialize_rows_for_response
from baserow.contrib.database.rows import signals as row_signals
from baserow.contrib.database.table.models import GeneratedTableModel
from baserow.contrib.database.views.handler import PublicViewRows, ViewHandler
from baserow.contrib.database.views.registries import view_type_registry
from baserow.contrib.database.ws.rows.signals import (
    RealtimeRowMessages,
    serialize_rows_values,
)
from baserow.core.telemetry.utils import baserow_trace
from baserow.ws.registries import page_registry

tracer = trace.get_tracer(__name__)


@baserow_trace(tracer)
def _send_rows_created_event_to_views(
    serialized_rows: List[Dict[Any, Any]],
    before: Optional[GeneratedTableModel],
    public_views: List[PublicViewRows],
):
    view_page_type = page_registry.get("view")
    handler = ViewHandler()

    for public_view, visible_row_ids in public_views:
        view_type = view_type_registry.get_by_model(public_view.specific_class)
        if not view_type.when_shared_publicly_requires_realtime_events:
            continue

        restricted_serialized_rows = handler.restrict_rows_for_view(
            public_view, serialized_rows, visible_row_ids
        )
        view_page_type.broadcast(
            RealtimeRowMessages.rows_created(
                table_id=PUBLIC_PLACEHOLDER_ENTITY_ID,
                serialized_rows=restricted_serialized_rows,
                metadata={},
                before=before,
            ),
            slug=public_view.slug,
        )


@baserow_trace(tracer)
def _send_rows_deleted_event_to_views(
    serialized_deleted_rows: List[Dict[Any, Any]],
    public_views: List[PublicViewRows],
):
    view_page_type = page_registry.get("view")
    handler = ViewHandler()
    for public_view, deleted_row_ids in public_views:
        view_type = view_type_registry.get_by_model(public_view.specific_class)
        if not view_type.when_shared_publicly_requires_realtime_events:
            continue

        restricted_serialized_deleted_rows = handler.restrict_rows_for_view(
            public_view, serialized_deleted_rows, deleted_row_ids
        )
        view_page_type.broadcast(
            RealtimeRowMessages.rows_deleted(
                table_id=PUBLIC_PLACEHOLDER_ENTITY_ID,
                serialized_rows=restricted_serialized_deleted_rows,
            ),
            slug=public_view.slug,
        )


@receiver(row_signals.rows_created)
@baserow_trace(tracer)
def public_rows_created(
    sender,
    rows,
    before,
    user,
    table,
    model,
    send_realtime_update=True,
    send_webhook_events=True,
    **kwargs,
):
    if not send_realtime_update:
        return

    row_checker = ViewHandler().get_public_views_row_checker(
        table, model, only_include_views_which_want_realtime_events=True
    )
    transaction.on_commit(
        lambda: _send_rows_created_event_to_views(
            serialize_rows_for_response(rows, model),
            before,
            row_checker.get_public_views_where_rows_are_visible(rows),
        ),
    )


@receiver(row_signals.before_rows_delete)
@baserow_trace(tracer)
def public_before_rows_delete(sender, rows, user, table, model, **kwargs):
    row_checker = ViewHandler().get_public_views_row_checker(
        table, model, only_include_views_which_want_realtime_events=True
    )
    return {
        "deleted_rows_public_views": (
            row_checker.get_public_views_where_rows_are_visible(rows)
        ),
        "deleted_rows": serialize_rows_for_response(rows, model),
    }


@receiver(row_signals.rows_deleted)
@baserow_trace(tracer)
def public_rows_deleted(
    sender, rows, user, table, model, before_return, send_realtime_update=True, **kwargs
):
    if not send_realtime_update:
        return

    public_views = dict(before_return)[public_before_rows_delete][
        "deleted_rows_public_views"
    ]
    serialized_deleted_rows = dict(before_return)[public_before_rows_delete][
        "deleted_rows"
    ]
    transaction.on_commit(
        lambda: _send_rows_deleted_event_to_views(serialized_deleted_rows, public_views)
    )


@receiver(row_signals.before_rows_update)
@baserow_trace(tracer)
def public_before_rows_update(
    sender, rows, user, table, model, updated_field_ids, **kwargs
):
    row_checker = ViewHandler().get_public_views_row_checker(
        table,
        model,
        only_include_views_which_want_realtime_events=True,
        updated_field_ids=updated_field_ids,
    )
    return {
        "old_rows_public_views": row_checker.get_public_views_where_rows_are_visible(
            rows
        ),
        "caching_row_checker": row_checker,
    }


@receiver(row_signals.rows_updated)
@baserow_trace(tracer)
def public_rows_updated(
    sender,
    rows,
    user,
    table,
    model,
    before_return,
    updated_field_ids,
    send_realtime_update=True,
    **kwargs,
):
    if not send_realtime_update:
        return

    before_return_dict = dict(before_return)[public_before_rows_update]
    serialized_old_rows = dict(before_return)[serialize_rows_values]
    serialized_updated_rows = serialize_rows_for_response(rows, model)

    old_row_public_views: List[PublicViewRows] = before_return_dict[
        "old_rows_public_views"
    ]
    existing_checker = before_return_dict["caching_row_checker"]
    public_view_rows: List[
        PublicViewRows
    ] = existing_checker.get_public_views_where_rows_are_visible(rows)

    view_slug_to_updated_public_view_rows = {
        view.view.slug: view for view in public_view_rows
    }

    # When a row is updated from the point of view of a public view it might not always
    # result in a `rows_updated` event. For example if a row was previously not visible
    # in the public view due to its filters, but the row update makes it now match
    # the filters we want to send a `rows_created` event to that views page as the
    # clients won't know anything about the row and hence a `rows_updated` event makes
    # no sense for them.
    public_views_where_rows_were_created: List[PublicViewRows] = []
    public_views_where_rows_were_updated: List[PublicViewRows] = []
    public_views_where_rows_were_deleted: List[PublicViewRows] = []

    for old_public_view_rows in old_row_public_views:
        (old_row_view, old_visible_ids) = old_public_view_rows

        updated_public_view_rows = view_slug_to_updated_public_view_rows.pop(
            old_row_view.slug, None
        )

        if updated_public_view_rows is None:
            public_views_where_rows_were_deleted.append(
                PublicViewRows(old_row_view, None)
            )
        else:
            new_visible_ids = updated_public_view_rows.allowed_row_ids

            if (
                old_visible_ids == PublicViewRows.ALL_ROWS_ALLOWED
                and new_visible_ids == PublicViewRows.ALL_ROWS_ALLOWED
            ):
                public_views_where_rows_were_updated.append(
                    PublicViewRows(old_row_view, PublicViewRows.ALL_ROWS_ALLOWED)
                )
                continue

            if old_visible_ids == PublicViewRows.ALL_ROWS_ALLOWED:
                old_visible_ids = new_visible_ids

            if new_visible_ids == PublicViewRows.ALL_ROWS_ALLOWED:
                new_visible_ids = old_visible_ids

            deleted_ids = old_visible_ids - new_visible_ids
            if len(deleted_ids) > 0:
                public_views_where_rows_were_deleted.append(
                    PublicViewRows(old_row_view, deleted_ids)
                )

            created_ids = new_visible_ids - old_visible_ids
            if len(created_ids) > 0:
                public_views_where_rows_were_created.append(
                    PublicViewRows(old_row_view, created_ids)
                )

            updated_ids = new_visible_ids - created_ids - deleted_ids
            if len(updated_ids) > 0:
                public_views_where_rows_were_updated.append(
                    PublicViewRows(old_row_view, updated_ids)
                )

    # Any remaining views in the updated_rows_public_views dict are views which
    # previously didn't show the old row, but now show the new row, so we want created.
    public_views_where_rows_were_created = public_views_where_rows_were_created + list(
        view_slug_to_updated_public_view_rows.values()
    )

    @baserow_trace(tracer)
    def _send_created_updated_deleted_row_signals_to_views():
        _send_rows_deleted_event_to_views(
            serialized_old_rows, public_views_where_rows_were_deleted
        )
        _send_rows_created_event_to_views(
            serialized_updated_rows,
            before=None,
            public_views=public_views_where_rows_were_created,
        )

        view_page_type = page_registry.get("view")
        handler = ViewHandler()

        for public_view, visible_row_ids in public_views_where_rows_were_updated:
            visible_fields_only_updated_rows = handler.restrict_rows_for_view(
                public_view, serialized_updated_rows, visible_row_ids
            )
            visible_fields_only_old_rows = handler.restrict_rows_for_view(
                public_view, serialized_old_rows, visible_row_ids
            )
            view_page_type.broadcast(
                RealtimeRowMessages.rows_updated(
                    table_id=PUBLIC_PLACEHOLDER_ENTITY_ID,
                    serialized_rows_before_update=visible_fields_only_old_rows,
                    serialized_rows=visible_fields_only_updated_rows,
                    updated_field_ids=list(updated_field_ids),
                    metadata={},
                ),
                slug=public_view.slug,
            )

    transaction.on_commit(_send_created_updated_deleted_row_signals_to_views)
