from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.core.context import clear_current_workspace_id, set_current_workspace_id
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.storage import get_default_storage


class CoreExportedFileURLSerializerMixin(serializers.Serializer):
    url = serializers.SerializerMethodField()

    def get_handler(self):
        """Define handler used for url generation.
        That handler needs to to implement method `export_file_path`.
        """

        raise NotImplementedError("Subclasses must implement this method.")

    def get_instance_attr(self, instance, name):
        return getattr(instance, name)

    @extend_schema_field(OpenApiTypes.URI)
    def get_url(self, instance):
        if hasattr(instance, "workspace_id"):
            # FIXME: Temporarily setting the current workspace ID for URL generation in
            # storage backends, enabling permission checks at download time.
            try:
                set_current_workspace_id(instance.workspace_id)
                return self._get_url(instance)
            finally:
                clear_current_workspace_id()
        else:
            return self._get_url(instance)

    def _get_url(self, instance):
        handler = self.get_handler()
        name = self.get_instance_attr(instance, "exported_file_name")
        if name:
            path = handler.export_file_path(name)
            storage = get_default_storage()
            return storage.url(path)
        else:
            return None


class ExportWorkspaceExportedFileURLSerializerMixin(CoreExportedFileURLSerializerMixin):
    def get_handler(self):
        return ImportExportHandler()
