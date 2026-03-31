from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.database.api.views.serializers import PublicViewInfoSerializer
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.views import signals as view_signals
from baserow.contrib.database.views.registries import view_type_registry
from baserow.core.db import specific_iterator
from baserow.ws.registries import page_registry


def _send_force_rows_refresh_if_view_public(view):
    view_page_type = page_registry.get("view")
    if view.public:
        transaction.on_commit(
            lambda: view_page_type.broadcast(
                {"type": "force_view_rows_refresh", "view_id": view.slug},
                None,
                slug=view.slug,
            )
        )


def _send_force_view_refresh_if_view_public(
    view,
):
    view_page_type = page_registry.get("view")
    view_type = view_type_registry.get_by_model(view.specific_class)

    if view.public and view_type.has_public_info:
        if not view_type.when_shared_publicly_requires_realtime_events:
            return

        def on_commit():
            field_options = view_type.get_visible_field_options_in_order(view)
            fields = specific_iterator(
                Field.objects.filter(id__in=field_options.values_list("field_id"))
                .select_related("content_type")
                .prefetch_related("select_options")
            )

            view_serialized = PublicViewInfoSerializer(
                view=view,
                fields=fields,
            ).data

            view_page_type.broadcast(
                {
                    "type": "force_view_refresh",
                    "view_id": view.slug,
                    **view_serialized,
                },
                None,
                slug=view.slug,
            )

        transaction.on_commit(on_commit)


@receiver(view_signals.view_updated)
def public_view_updated(sender, view, user, **kwargs):
    _send_force_view_refresh_if_view_public(view)


@receiver(view_signals.view_filter_created)
def public_view_filter_created(sender, view_filter, user, **kwargs):
    _send_force_rows_refresh_if_view_public(view_filter.view)


@receiver(view_signals.view_filter_updated)
def public_view_filter_updated(sender, view_filter, user, **kwargs):
    _send_force_rows_refresh_if_view_public(view_filter.view)


@receiver(view_signals.view_filter_deleted)
def public_view_filter_deleted(sender, view_filter_id, view_filter, user, **kwargs):
    _send_force_rows_refresh_if_view_public(view_filter.view)


@receiver(view_signals.view_group_by_created)
def public_view_group_by_created(sender, view_group_by, user, **kwargs):
    _send_force_view_refresh_if_view_public(view_group_by.view)


@receiver(view_signals.view_group_by_updated)
def public_view_group_by_updated(sender, view_group_by, user, **kwargs):
    _send_force_view_refresh_if_view_public(view_group_by.view)


@receiver(view_signals.view_group_by_deleted)
def public_view_group_by_deleted(
    sender, view_group_by_id, view_group_by, user, **kwargs
):
    _send_force_view_refresh_if_view_public(view_group_by.view)


@receiver(view_signals.view_field_options_updated)
def public_view_field_options_updated(sender, view, user, **kwargs):
    _send_force_view_refresh_if_view_public(view)
