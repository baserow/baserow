from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.services.serializers import (
    PolymorphicServiceSerializer,
    ServiceSerializer,
)
from baserow.contrib.database.table.operations import ReadDatabaseTableOperationType
from baserow.core.handler import CoreHandler


class DatabaseServiceSerializer(ServiceSerializer):
    """
    A service as a button field's editor sees it. The schema describes the
    table the action writes to, which is not always a table the reader may
    see, so it is only included when they may.
    """

    table_accessible = serializers.SerializerMethodField(
        help_text="Whether the reader may see the table this service writes to. "
        "The schema is left out when they may not."
    )

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_table_accessible(self, instance) -> bool:
        service = instance.specific
        table = getattr(service, "table", None)
        if table is None:
            # Nothing to hide until a table has been chosen.
            return True

        user = self.context.get("user")
        if user is None:
            return False

        return CoreHandler().check_permissions(
            user,
            ReadDatabaseTableOperationType.type,
            workspace=table.database.workspace,
            context=table,
            raise_permission_exceptions=False,
        )

    def get_schema(self, instance):
        if not self.get_table_accessible(instance):
            return None
        return super().get_schema(instance)

    def get_context_data(self, instance):
        if not self.get_table_accessible(instance):
            return None
        return super().get_context_data(instance)

    def get_context_data_schema(self, instance):
        if not self.get_table_accessible(instance):
            return None
        return super().get_context_data_schema(instance)

    class Meta(ServiceSerializer.Meta):
        fields = ServiceSerializer.Meta.fields + ("table_accessible",)


class DatabasePolymorphicServiceSerializer(PolymorphicServiceSerializer):
    base_class = DatabaseServiceSerializer
