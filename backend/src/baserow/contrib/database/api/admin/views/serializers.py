from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.registries import view_type_registry


class AdminViewSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    table_id = serializers.IntegerField(read_only=True)
    table_name = serializers.CharField(source="table.name", read_only=True)
    database_id = serializers.IntegerField(source="table.database_id", read_only=True)
    database_name = serializers.CharField(source="table.database.name", read_only=True)
    workspace_id = serializers.IntegerField(
        source="table.database.workspace_id", read_only=True
    )
    workspace_name = serializers.CharField(
        source="table.database.workspace.name", read_only=True
    )
    public_view_has_password = serializers.BooleanField(read_only=True)
    owned_by_id = serializers.IntegerField(read_only=True)
    owned_by_username = serializers.SerializerMethodField()

    class Meta:
        model = View
        fields = (
            "id",
            "name",
            "slug",
            "type",
            "table_id",
            "table_name",
            "database_id",
            "database_name",
            "workspace_id",
            "workspace_name",
            "public",
            "public_view_has_password",
            "owned_by_id",
            "owned_by_username",
            "ownership_type",
            "created_on",
        )

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return view_type_registry.get_by_model(instance.specific_class).type

    @extend_schema_field(OpenApiTypes.STR)
    def get_owned_by_username(self, instance):
        return instance.owned_by.username if instance.owned_by_id else None


class AdminViewUpdateSerializer(serializers.ModelSerializer):
    public = serializers.BooleanField(
        required=True,
        help_text="Indicates whether the view must be publicly shared.",
    )

    class Meta:
        model = View
        fields = ("public",)
