from copy import deepcopy

from django.db.models import Q

from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.ws.views.rows.registries import ViewRealtimeRowsType
from baserow.ws.registries import page_registry


class PublicViewRealtimeRowsType(ViewRealtimeRowsType):
    type = "public_view"

    def get_views_filter(self) -> Q:
        return Q(public=True)

    def broadcast(self, view, payload):
        view_page_type = page_registry.get("view")
        payload = deepcopy(payload)
        payload["table_id"] = PUBLIC_PLACEHOLDER_ENTITY_ID
        view_page_type.broadcast(
            payload,
            slug=view.slug,
        )
