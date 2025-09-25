from django.db.models import Q

from baserow.contrib.database.ws.views.rows.registries import ViewRealtimeRowsType
from baserow.ws.registries import page_registry
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType


class RestrictedViewRealtimeRowsType(ViewRealtimeRowsType):
    type = "restricted_view"

    def get_views_filter(self) -> Q:
        return Q(ownership_type=RestrictedViewOwnershipType.type)

    def broadcast(self, view, payload):
        view_page_type = page_registry.get("restricted_view")
        view_page_type.broadcast(
            payload,
            restricted_view_id=view.id,
        )
