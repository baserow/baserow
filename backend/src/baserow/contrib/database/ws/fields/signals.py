from typing import Iterable, Optional, Type

from django.db import transaction
from django.dispatch import receiver

from rest_framework.serializers import Serializer

from baserow.contrib.database.api.fields.serializers import FieldSerializer
from baserow.contrib.database.api.views.serializers import (
    FieldWithFiltersAndSortsSerializer,
)
from baserow.contrib.database.fields import signals as field_signals
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.registries import (
    field_extension_registry,
    field_type_registry,
)
from baserow.ws.registries import page_registry


@receiver(field_signals.field_created)
def field_created(sender, field, related_fields, user, **kwargs):
    table_page_type = page_registry.get("table")
    transaction.on_commit(
        lambda: table_page_type.broadcast(
            RealtimeFieldMessages.field_created(
                field,
                related_fields,
            ),
            getattr(user, "web_socket_id", None),
            table_id=field.table_id,
        )
    )


@receiver(field_signals.field_restored)
def field_restored(sender, field, related_fields, user, **kwargs):
    table_page_type = page_registry.get("table")
    transaction.on_commit(
        lambda: table_page_type.broadcast(
            RealtimeFieldMessages.field_restored(
                field,
                related_fields,
            ),
            getattr(user, "web_socket_id", None),
            table_id=field.table_id,
        )
    )


@receiver(field_signals.field_updated)
def field_updated(sender, field, related_fields, user, **kwargs):
    table_page_type = page_registry.get("table")
    transaction.on_commit(
        lambda: table_page_type.broadcast(
            RealtimeFieldMessages.field_updated(
                field,
                related_fields,
            ),
            getattr(user, "web_socket_id", None),
            table_id=field.table_id,
        )
    )


@receiver(field_signals.field_deleted)
def field_deleted(
    sender, field_id, field, related_fields, user, before_return, **kwargs
):
    table_page_type = page_registry.get("table")
    transaction.on_commit(
        lambda: table_page_type.broadcast(
            RealtimeFieldMessages.field_deleted(
                field.table_id,
                field_id,
                related_fields,
            ),
            getattr(user, "web_socket_id", None),
            table_id=field.table_id,
        )
    )


class RealtimeFieldMessages:
    """
    A collection of functions which construct the payloads for the realtime
    websocket messages related to fields.
    """

    @staticmethod
    def serialize_field_for_websockets(
        field: Field, field_serializer_class: Optional[Type[Serializer]] = None
    ):
        if field_serializer_class is None:
            field_serializer_class = FieldSerializer
        return field_type_registry.get_serializer(field, field_serializer_class).data

    @staticmethod
    def serialize_fields_for_websockets(
        fields: Iterable[Field],
        field_serializer_class: Optional[Type[Serializer]] = None,
    ):
        if field_serializer_class is None:
            field_serializer_class = FieldSerializer
        fields = list(fields)
        field_extension_registry.prefetch_fields(fields)
        return [
            field_type_registry.get_serializer(f, field_serializer_class).data
            for f in fields
        ]

    @staticmethod
    def field_created(
        field: Field,
        related_fields: Iterable[Field],
        field_serializer_class: Optional[Type[Serializer]] = None,
    ):
        return {
            "type": "field_created",
            "field": RealtimeFieldMessages.serialize_field_for_websockets(
                field, field_serializer_class=field_serializer_class
            ),
            "related_fields": RealtimeFieldMessages.serialize_fields_for_websockets(
                related_fields, field_serializer_class=field_serializer_class
            ),
        }

    @staticmethod
    def field_restored(
        field: Field,
        related_fields: Iterable[Field],
        field_serializer_class: Optional[Type[Serializer]] = None,
    ):
        if field_serializer_class is None:
            field_serializer_class = FieldWithFiltersAndSortsSerializer
        return {
            "type": "field_restored",
            "field": RealtimeFieldMessages.serialize_field_for_websockets(
                field, field_serializer_class=field_serializer_class
            ),
            "related_fields": RealtimeFieldMessages.serialize_fields_for_websockets(
                related_fields, field_serializer_class=field_serializer_class
            ),
        }

    @staticmethod
    def field_updated(
        field: Field,
        related_fields: Iterable[Field],
        field_serializer_class: Optional[Type[Serializer]] = None,
    ):
        return {
            "type": "field_updated",
            "field_id": field.id,
            "field": RealtimeFieldMessages.serialize_field_for_websockets(
                field, field_serializer_class=field_serializer_class
            ),
            "related_fields": RealtimeFieldMessages.serialize_fields_for_websockets(
                related_fields, field_serializer_class=field_serializer_class
            ),
        }

    @staticmethod
    def field_deleted(
        table_id: int,
        field_id: int,
        related_fields: Iterable[Field],
        field_serializer_class: Optional[Type[Serializer]] = None,
    ):
        return {
            "type": "field_deleted",
            "table_id": table_id,
            "field_id": field_id,
            "related_fields": RealtimeFieldMessages.serialize_fields_for_websockets(
                related_fields, field_serializer_class=field_serializer_class
            ),
        }
