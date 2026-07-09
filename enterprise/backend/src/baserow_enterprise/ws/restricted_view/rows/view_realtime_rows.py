from django.db.models import Q

from baserow.contrib.database.ws.views.rows.registries import ViewRealtimeRowsType
from baserow.ws.registries import page_registry
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType


class RestrictedViewRealtimeRowsType(ViewRealtimeRowsType):
    type = "restricted_view"

    def get_views_filter(self) -> Q:
        return Q(ownership_type=RestrictedViewOwnershipType.type)

    def broadcast(self, view, payload, user=None):
        view_page_type = page_registry.get("restricted_view")
        # Restricted clients have no filters; the editor needs its own create/delete.
        editor_needs_own_event = payload.get("type") in (
            "rows_created",
            "rows_deleted",
        )
        ignore_web_socket_id = (
            None if editor_needs_own_event else getattr(user, "web_socket_id", None)
        )
        view_page_type.broadcast(
            payload,
            ignore_web_socket_id=ignore_web_socket_id,
            restricted_view_id=view.id,
        )
