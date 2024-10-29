from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.applications.serializers import (
    PolymorphicApplicationResponseSerializer,
)
from baserow.api.serializers import FileURLSerializerMixin
from baserow.core.db import specific_iterator
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.models import Application, ImportExportResource


class ImportResourceSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    def get_name(self, instance):
        return (
            instance.original_name
            if instance.original_name
            else instance.get_archive_name()
        )

    class Meta:
        model = ImportExportResource
        fields = ("id", "name", "size")


class ExportWorkspaceExportedFileURLSerializerMixin(FileURLSerializerMixin):
    exported_file_name = serializers.SerializerMethodField()

    def _get_exported_file_name(self, instance):
        resource = instance.resource
        return resource.get_archive_name() if resource else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_exported_file_name(self, instance):
        resource_file_name = self._get_exported_file_name(instance)
        return f"export_{resource_file_name}" if resource_file_name else None

    def get_handler(self):
        return ImportExportHandler()


class InstalledApplicationsSerializer(serializers.JSONField):
    def to_representation(self, value):
        if not value:
            return None

        applications = specific_iterator(
            Application.objects.select_related("content_type", "workspace").filter(
                pk__in=value, workspace__trashed=False
            )
        )
        return [
            PolymorphicApplicationResponseSerializer(app).data for app in applications
        ]
