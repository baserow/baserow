from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.services.serializers import ServiceSerializer, UpdateServiceSerializer
from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.data_sources.records import DashboardTableRecordsService
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.core.exceptions import PermissionException


class DashboardDataSourceSerializer(ServiceSerializer):
    """
    Basic data source serializer mostly for returned values.
    This serializer flatten the service properties so that from
    an API POV only the data source object exists.
    """

    id = serializers.SerializerMethodField(help_text="Data source id.")
    name = serializers.SerializerMethodField(
        help_text=DashboardDataSource._meta.get_field("name").help_text
    )
    dashboard_id = serializers.SerializerMethodField(
        help_text=DashboardDataSource._meta.get_field("dashboard").help_text
    )
    order = serializers.SerializerMethodField(
        help_text=DashboardDataSource._meta.get_field("order").help_text
    )
    type = serializers.SerializerMethodField(help_text="The type of the data source.")
    table_schema = serializers.SerializerMethodField(
        help_text="The rows and fields of the underlying table, before aggregation."
    )

    def _get_service_instance(self, instance):
        # We generate the service schema using a `Service` instance.
        # If the `instance` is a `DashboardDataSource` instance, traverse its
        # 1-1 relation to `Service` and serialize it.
        return (
            instance.service if isinstance(instance, DashboardDataSource) else instance
        )

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        service_instance = self._get_service_instance(instance)
        if service_instance:
            return super().get_type(service_instance)
        else:
            return None

    @extend_schema_field(OpenApiTypes.INT)
    def get_id(self, instance):
        return self.context["data_source"].id

    @extend_schema_field(OpenApiTypes.STR)
    def get_name(self, instance):
        return self.context["data_source"].name

    @extend_schema_field(OpenApiTypes.INT)
    def get_dashboard_id(self, instance):
        return self.context["data_source"].dashboard_id

    @extend_schema_field(OpenApiTypes.STR)
    def get_order(self, instance):
        return str(self.context["data_source"].order)

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_schema(self, instance):
        service_instance = self._get_service_instance(instance)
        if service_instance:
            return super().get_schema(service_instance)
        return None

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_context_data(self, instance):
        service_instance = self._get_service_instance(instance)
        if service_instance:
            return super().get_context_data(service_instance)
        else:
            return {}

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_context_data_schema(self, instance):
        service_instance = self._get_service_instance(instance)
        if service_instance:
            return super().get_context_data_schema(service_instance)
        else:
            return None

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_table_schema(self, instance):
        from baserow.contrib.integrations.local_baserow.service_types import (
            LocalBaserowTableServiceType,
        )

        service = self._get_service_instance(instance)
        # Shared websocket messages cannot carry recipient-specific schemas.
        request = self.context.get("request")
        if service is None or request is None:
            return None
        service = service.specific
        service_type = service.get_type()
        if (
            not isinstance(service_type, LocalBaserowTableServiceType)
            or not service.table_id
        ):
            return None
        try:
            table = DashboardTableRecordsService().get_readable_table(
                request.user, service.table_id
            )
        except (PermissionException, TableDoesNotExist):
            return None
        return {
            "title": table.name,
            "type": "array",
            "items": {
                "type": "object",
                "properties": service_type.get_table_properties(service),
            },
        }

    class Meta(ServiceSerializer.Meta):
        fields = ServiceSerializer.Meta.fields + (
            "name",
            "dashboard_id",
            "order",
            "table_schema",
        )
        extra_kwargs = {
            **ServiceSerializer.Meta.extra_kwargs,
            "name": {"read_only": True},
            "dashboard_id": {"read_only": True},
            "order": {"read_only": True, "help_text": "Lowest first."},
        }


class UpdateDashboardDataSourceSerializer(UpdateServiceSerializer):
    name = serializers.CharField(required=False)

    class Meta(ServiceSerializer.Meta):
        fields = UpdateServiceSerializer.Meta.fields + ("name",)
