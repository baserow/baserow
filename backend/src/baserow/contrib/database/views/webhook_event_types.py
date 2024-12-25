from django.contrib.auth.models import AnonymousUser

from baserow.contrib.database.api.views.serializers import ViewSerializer
from baserow.contrib.database.webhooks.registries import WebhookEventType

from .models import GridView
from .registries import view_type_registry
from .signals import view_created, view_deleted, view_updated


class ViewEventType(WebhookEventType):
    def get_payload(self, event_id, webhook, view, user, **kwargs):
        payload = super().get_payload(event_id, webhook, **kwargs)
        serializer = view_type_registry.get_serializer(
            view, ViewSerializer, context={"user": user}
        )
        payload["view"] = serializer.data
        return payload

    def get_test_call_payload(self, table, model, event_id, webhook):
        view = GridView(id=0, name="View", table_id=0, order=1)
        payload = self.get_payload(
            event_id=event_id, webhook=webhook, view=view, user=AnonymousUser
        )
        return payload

    def get_table_object(self, view, **kwargs):
        return view.table


class ViewCreatedEventType(ViewEventType):
    type = "view.created"
    signal = view_created


class ViewUpdatedEventType(ViewEventType):
    type = "view.updated"
    signal = view_updated


class ViewDeletedEventType(WebhookEventType):
    type = "view.deleted"
    signal = view_deleted

    def get_payload(self, event_id, webhook, view_id, **kwargs):
        payload = super().get_payload(event_id, webhook, **kwargs)
        payload["view_id"] = view_id
        return payload

    def get_test_call_payload(self, table, model, event_id, webhook):
        payload = self.get_payload(
            event_id=event_id,
            webhook=webhook,
            view_id=1,
            table=table,
        )
        return payload

    def get_table_object(self, view, **kwargs):
        return view.table
