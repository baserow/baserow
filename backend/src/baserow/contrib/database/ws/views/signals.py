from django.db import transaction
from django.db.models import prefetch_related_objects
from django.dispatch import receiver

from baserow.contrib.database.api.views.serializers import (
    ViewDecorationSerializer,
    ViewFilterGroupSerializer,
    ViewFilterSerializer,
    ViewGroupBySerializer,
    ViewSerializer,
    ViewSortSerializer,
)
from baserow.contrib.database.views import signals as view_signals
from baserow.contrib.database.views.registries import (
    view_ownership_type_registry,
    view_type_registry,
)
from baserow.ws.registries import page_registry
from baserow.ws.tasks import broadcast_to_users


def _prefetch_view_default_values(view):
    """Prefetches view_default_values for efficient serialization."""

    if (
        not hasattr(view, "_prefetched_objects_cache")
        or "view_default_values" not in view._prefetched_objects_cache
    ):
        prefetch_related_objects([view], "view_default_values")


def generate_view_created_payload(user, view):
    _prefetch_view_default_values(view)
    payload = {
        "type": "view_created",
        "view": view_type_registry.get_serializer(
            view,
            ViewSerializer,
            filters=True,
            sortings=True,
            decorations=True,
            group_bys=True,
            default_row_values=True,
            context={"user": user},
        ).data,
    }
    return payload


def generate_view_deleted_payload(table_id, view_id):
    payload = {
        "type": "view_deleted",
        "table_id": table_id,
        "view_id": view_id,
    }
    return payload


def broadcast_view_updated_payload_to_owner(user, user_ids, payload):
    transaction.on_commit(
        lambda: broadcast_to_users.delay(
            user_ids,
            payload,
            getattr(user, "web_socket_id", None),
        )
    )


def broadcast_to(user, view, payload):
    ownership_type = view_ownership_type_registry.get(view.ownership_type)
    broadcast_type, user_ids = ownership_type.should_broadcast_signal_to(view)

    if broadcast_type == "users":
        transaction.on_commit(
            lambda: broadcast_to_users.delay(
                user_ids,
                payload,
                getattr(user, "web_socket_id", None),
            )
        )

    if broadcast_type == "table":
        table_page_type = page_registry.get("table")
        transaction.on_commit(
            lambda: table_page_type.broadcast(
                payload,
                getattr(user, "web_socket_id", None),
                table_id=view.table_id,
            )
        )


@receiver(view_signals.view_created)
def view_created(sender, view, user, **kwargs):
    payload = generate_view_created_payload(user, view)
    broadcast_to(user, view, payload)


def is_view_ownership_type_changed(new_view, old_view):
    return old_view.ownership_type != new_view.ownership_type


def broadcast_to_users_ownership_change(user, new_view, old_view, payload):
    """
    Broadcasts the payload to the users that are affected by the ownership
    change. Depending on ownership types, we might want to broadcast to some
    specific users (broadcast_type="users") or to all users that have access to
    a table (broadcast_type="table"). This function takes care of sending
    the correct type of signal to the correct users.

    :param user: The user that triggered the ownership change.
    :param new_view: The view that has been updated.
    :param old_view: The view before the update.
    :param payload: The payload that needs to be broadcasted.

    """

    old_view_ownership_type = view_ownership_type_registry.get(old_view.ownership_type)
    new_view_ownership_type = view_ownership_type_registry.get(new_view.ownership_type)

    (
        old_broadcast_type,
        old_view_user_ids,
    ) = old_view_ownership_type.should_broadcast_signal_to(new_view)
    (
        new_broadcast_type,
        new_view_user_ids,
    ) = new_view_ownership_type.should_broadcast_signal_to(new_view)

    table_page_type = page_registry.get("table")
    if old_broadcast_type == "table" and new_broadcast_type == "users":
        # broadcast `view_deleted` payload to users in the table, except the owner of
        # the view.
        transaction.on_commit(
            lambda: table_page_type.broadcast(
                generate_view_deleted_payload(new_view.table_id, new_view.id),
                getattr(user, "web_socket_id", None),
                table_id=new_view.table_id,
                exclude_user_ids=new_view_user_ids,
            )
        )
        # broadcast `view_updated` payload to owner of the view.
        broadcast_view_updated_payload_to_owner(user, new_view_user_ids, payload)
    elif old_broadcast_type == "users" and new_broadcast_type == "table":
        # broadcast `view_created` payload to users in the table, except the owner of
        # the view.
        transaction.on_commit(
            lambda: table_page_type.broadcast(
                generate_view_created_payload(user, new_view),
                getattr(user, "web_socket_id", None),
                table_id=new_view.table_id,
                exclude_user_ids=old_view_user_ids,
            )
        )

        # broadcast `view_updated` payload to owner of the view.
        broadcast_view_updated_payload_to_owner(user, old_view_user_ids, payload)
    else:
        broadcast_to(user, new_view, payload)


@receiver(view_signals.view_updated)
def view_updated(sender, view, old_view, user, **kwargs):
    _prefetch_view_default_values(view)
    payload = {
        "type": "view_updated",
        "view_id": view.id,
        "view": view_type_registry.get_serializer(
            view,
            ViewSerializer,
            # We do not want to broad cast the filters, decorations and sortings
            # every time the view changes.
            # There are separate views and handlers for them
            # each will broad cast their own message.
            filters=False,
            sortings=False,
            decorations=False,
            group_bys=False,
            default_row_values=True,
            context={"user": user},
        ).data,
    }

    if is_view_ownership_type_changed(view, old_view):
        broadcast_to_users_ownership_change(user, view, old_view, payload)
    else:
        broadcast_to(user, view, payload)


@receiver(view_signals.view_deleted)
def view_deleted(sender, view_id, view, user, **kwargs):
    payload = generate_view_deleted_payload(view.table_id, view_id)
    broadcast_to(user, view, payload)


@receiver(view_signals.views_reordered)
def views_reordered(sender, table, order, user, **kwargs):
    payload = {"type": "views_reordered", "table_id": table.id, "order": order}

    first_view = table.view_set.get(id=order[0])

    # Here we are assuming that the views are all broadcasted the same way as they are
    # and there should be from the same "owner"
    broadcast_to(user, first_view, payload)


@receiver(view_signals.view_filter_created)
def view_filter_created(sender, view_filter, user, **kwargs):
    payload = {
        "type": "view_filter_created",
        "view_filter": ViewFilterSerializer(view_filter).data,
    }

    broadcast_to(user, view_filter.view, payload)


@receiver(view_signals.view_filter_updated)
def view_filter_updated(sender, view_filter, user, **kwargs):
    payload = {
        "type": "view_filter_updated",
        "view_filter_id": view_filter.id,
        "view_filter": ViewFilterSerializer(view_filter).data,
    }

    broadcast_to(user, view_filter.view, payload)


@receiver(view_signals.view_filter_deleted)
def view_filter_deleted(sender, view_filter_id, view_filter, user, **kwargs):
    payload = {
        "type": "view_filter_deleted",
        "view_id": view_filter.view_id,
        "view_filter_id": view_filter_id,
    }

    broadcast_to(user, view_filter.view, payload)


@receiver(view_signals.view_filter_group_created)
def view_filter_group_created(sender, view_filter_group, user, **kwargs):
    payload = {
        "type": "view_filter_group_created",
        "view_filter_group": ViewFilterGroupSerializer(view_filter_group).data,
    }

    broadcast_to(user, view_filter_group.view, payload)


@receiver(view_signals.view_filter_group_updated)
def view_filter_group_updated(sender, view_filter_group, user, **kwargs):
    payload = {
        "type": "view_filter_group_updated",
        "view_filter_group_id": view_filter_group.id,
        "view_filter_group": ViewFilterGroupSerializer(view_filter_group).data,
    }

    broadcast_to(user, view_filter_group.view, payload)


@receiver(view_signals.view_filter_group_deleted)
def view_filter_group_deleted(
    sender, view_filter_group_id, view_filter_group, user, **kwargs
):
    payload = {
        "type": "view_filter_group_deleted",
        "view_id": view_filter_group.view_id,
        "view_filter_group_id": view_filter_group_id,
    }

    broadcast_to(user, view_filter_group.view, payload)


@receiver(view_signals.view_sort_created)
def view_sort_created(sender, view_sort, user, **kwargs):
    payload = {
        "type": "view_sort_created",
        "view_sort": ViewSortSerializer(view_sort).data,
    }

    broadcast_to(user, view_sort.view, payload)


@receiver(view_signals.view_sort_updated)
def view_sort_updated(sender, view_sort, user, **kwargs):
    payload = {
        "type": "view_sort_updated",
        "view_sort_id": view_sort.id,
        "view_sort": ViewSortSerializer(view_sort).data,
    }

    broadcast_to(user, view_sort.view, payload)


@receiver(view_signals.view_sort_deleted)
def view_sort_deleted(sender, view_sort_id, view_sort, user, **kwargs):
    payload = {
        "type": "view_sort_deleted",
        "view_id": view_sort.view_id,
        "view_sort_id": view_sort_id,
    }

    broadcast_to(user, view_sort.view, payload)


@receiver(view_signals.view_group_by_created)
def view_group_by_created(sender, view_group_by, user, **kwargs):
    payload = {
        "type": "view_group_by_created",
        "view_group_by": ViewGroupBySerializer(view_group_by).data,
    }

    broadcast_to(user, view_group_by.view, payload)


@receiver(view_signals.view_group_by_updated)
def view_group_by_updated(sender, view_group_by, user, **kwargs):
    payload = {
        "type": "view_group_by_updated",
        "view_group_by_id": view_group_by.id,
        "view_group_by": ViewGroupBySerializer(view_group_by).data,
    }

    broadcast_to(user, view_group_by.view, payload)


@receiver(view_signals.view_group_by_deleted)
def view_group_by_deleted(sender, view_group_by_id, view_group_by, user, **kwargs):
    payload = {
        "type": "view_group_by_deleted",
        "view_id": view_group_by.view_id,
        "view_group_by_id": view_group_by_id,
    }

    broadcast_to(user, view_group_by.view, payload)


@receiver(view_signals.view_decoration_created)
def view_decoration_created(sender, view_decoration, user, **kwargs):
    payload = {
        "type": "view_decoration_created",
        "view_decoration": ViewDecorationSerializer(view_decoration).data,
    }

    broadcast_to(user, view_decoration.view, payload)


@receiver(view_signals.view_decoration_updated)
def view_decoration_updated(sender, view_decoration, user, **kwargs):
    payload = {
        "type": "view_decoration_updated",
        "view_decoration_id": view_decoration.id,
        "view_decoration": ViewDecorationSerializer(view_decoration).data,
    }

    broadcast_to(user, view_decoration.view, payload)


@receiver(view_signals.view_decoration_deleted)
def view_decoration_deleted(
    sender, view_decoration_id, view_decoration, user, **kwargs
):
    payload = {
        "type": "view_decoration_deleted",
        "view_id": view_decoration.view_id,
        "view_decoration_id": view_decoration_id,
    }

    broadcast_to(user, view_decoration.view, payload)


@receiver(view_signals.view_field_options_updated)
def view_field_options_updated(sender, view, user, **kwargs):
    view_type = view_type_registry.get_by_model(view.specific_class)
    serializer_class = view_type.get_field_options_serializer_class(
        create_if_missing=False
    )
    payload = {
        "type": "view_field_options_updated",
        "view_id": view.id,
        "field_options": serializer_class(view).data["field_options"],
    }

    broadcast_to(user, view, payload)
