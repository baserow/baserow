from typing import Any

from django.core.files.storage import Storage
from django.db import transaction
from django.db.transaction import Atomic
from django.urls import include, path

from baserow.contrib.whiteboard.models import Whiteboard
from baserow.contrib.whiteboard.types import WhiteboardDict
from baserow.core.models import Application, Workspace
from baserow.core.registries import ApplicationType, ImportExportConfig
from baserow.core.storage import ExportZipFile
from baserow.core.utils import ChildProgressBuilder


class WhiteboardApplicationType(ApplicationType):
    type = "whiteboard"
    model_class = Whiteboard
    serializer_field_names = ["name"]
    allowed_fields = []
    supports_integrations = False
    supports_user_sources = False
    supports_actions = False

    def get_api_urls(self):
        from .api import urls as api_urls

        return [
            path("whiteboard/", include(api_urls, namespace=self.type)),
        ]

    def export_safe_transaction_context(self, application: Application) -> Atomic:
        return transaction.atomic()

    def export_serialized(
        self,
        whiteboard: Whiteboard,
        import_export_config: ImportExportConfig,
        files_zip: ExportZipFile | None = None,
        storage: Storage | None = None,
        progress_builder: ChildProgressBuilder | None = None,
    ) -> WhiteboardDict:
        """
        Exports the whiteboard application to a serialized dict that can later be
        imported via the `import_serialized` method.
        """

        serialized = super().export_serialized(
            whiteboard,
            import_export_config,
            files_zip=files_zip,
            storage=storage,
            progress_builder=progress_builder,
        )

        return WhiteboardDict(
            content=whiteboard.content or {},
            **serialized,
        )

    def import_serialized(
        self,
        workspace: Workspace,
        serialized_values: dict[str, Any],
        import_export_config: ImportExportConfig,
        id_mapping: dict[str, dict[int, int]],
        files_zip: ExportZipFile | None = None,
        storage: Storage | None = None,
        cache: dict[str, Any] | None = None,
        progress_builder: ChildProgressBuilder | None = None,
    ) -> Application:
        """
        Imports a whiteboard application exported by `export_serialized`.
        """

        content = serialized_values.pop("content", {})

        application = super().import_serialized(
            workspace,
            serialized_values,
            import_export_config,
            id_mapping,
            files_zip,
            storage,
            progress_builder,
        )

        if content:
            application.content = content
            application.save()

        return application
