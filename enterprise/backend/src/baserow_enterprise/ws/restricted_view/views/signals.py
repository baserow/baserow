from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.database.views import signals as view_signals
from baserow.contrib.database.views.registries import view_type_registry
from baserow.ws.registries import page_registry
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType


def _send_force_rows_refresh_if_view_restricted(view):
    view_page_type = page_registry.get("restricted_view")
    view_type = view_type_registry.get_by_model(view.specific_class)
    if (
        view.ownership_type == RestrictedViewOwnershipType.type
        and
        # This will make sure that the form view is excluded because there is no need
        # for real-time updates of a row in the form view.
        view_type.can_filter
    ):
        transaction.on_commit(
            lambda: view_page_type.broadcast(
                {"type": "force_view_rows_refresh", "view_id": view.id},
                None,
                restricted_view_id=view.id,
            )
        )


@receiver(view_signals.view_filter_created)
def restricted_view_filter_created(sender, view_filter, user, **kwargs):
    _send_force_rows_refresh_if_view_restricted(view_filter.view)


@receiver(view_signals.view_filter_updated)
def restricted_view_filter_updated(sender, view_filter, user, **kwargs):
    _send_force_rows_refresh_if_view_restricted(view_filter.view)


@receiver(view_signals.view_filter_deleted)
def restricted_view_filter_deleted(sender, view_filter_id, view_filter, user, **kwargs):
    _send_force_rows_refresh_if_view_restricted(view_filter.view)
