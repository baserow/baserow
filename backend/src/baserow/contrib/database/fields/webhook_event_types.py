from baserow.contrib.database.api.fields.serializers import FieldSerializer
from baserow.contrib.database.webhooks.registries import WebhookEventType

from .models import TextField
from .registries import field_type_registry
from .signals import field_created, field_deleted, field_updated


class FieldEventType(WebhookEventType):
    def get_payload(self, event_id, webhook, field, **kwargs):
        payload = super().get_payload(event_id, webhook, **kwargs)
        serializer = field_type_registry.get_serializer(field, FieldSerializer)
        payload["field"] = serializer.data
        return payload

    def get_test_call_payload(self, table, model, event_id, webhook):
        field = TextField(id=0, name="Field", table_id=0, order=1, primary=False)
        payload = self.get_payload(
            event_id=event_id,
            webhook=webhook,
            field=field,
        )
        return payload

    def get_table_object(self, field, **kwargs):
        return field.table


class FieldCreatedEventType(FieldEventType):
    type = "field.created"
    signal = field_created


class FieldUpdatedEventType(FieldEventType):
    type = "field.updated"
    signal = field_updated


class FieldDeletedEventType(WebhookEventType):
    type = "field.deleted"
    signal = field_deleted

    def get_payload(self, event_id, webhook, field_id, **kwargs):
        payload = super().get_payload(event_id, webhook, **kwargs)
        payload["field_id"] = field_id
        return payload

    def get_test_call_payload(self, table, model, event_id, webhook):
        payload = self.get_payload(
            event_id=event_id,
            webhook=webhook,
            field_id=1,
            table=table,
        )
        return payload

    def get_table_object(self, field, **kwargs):
        return field.table
