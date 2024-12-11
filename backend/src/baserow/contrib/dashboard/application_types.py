from typing import Any, Dict, Optional
from zipfile import ZipFile

from django.core.files.storage import Storage
from django.db import transaction
from django.db.transaction import Atomic
from django.urls import include, path

from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.dashboard.types import DashboardDict
from baserow.contrib.integrations.local_baserow.integration_types import (
    LocalBaserowIntegrationType,
)
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.models import Application, Workspace
from baserow.core.registries import ApplicationType, ImportExportConfig
from baserow.core.storage import ExportZipFile
from baserow.core.utils import ChildProgressBuilder


class DashboardApplicationType(ApplicationType):
    type = "dashboard"
    model_class = Dashboard
    serializer_field_names = ["name", "description"]
    allowed_fields = ["description"]
    supports_integrations = True

    def get_api_urls(self):
        from .api import urls as api_urls

        return [
            path("dashboard/", include(api_urls, namespace=self.type)),
        ]

    def export_safe_transaction_context(self, application: Application) -> Atomic:
        return transaction.atomic()

    def init_application(self, user, application: "Application") -> None:
        IntegrationHandler().create_integration(
            integration_type=integration_type_registry.get(
                LocalBaserowIntegrationType.type
            ),
            application=application,
            authorized_user=user,
        )

    def export_serialized(
        self,
        dashboard: Dashboard,
        import_export_config: ImportExportConfig,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
    ) -> DashboardDict:
        """
        Exports the dashboard application type to a serialized format that can later
        be imported via the `import_serialized`.
        """

        self.cache = {}
        serialized_dashboard = super().export_serialized(
            dashboard,
            import_export_config,
            files_zip=files_zip,
            storage=storage,
        )
        return DashboardDict(
            description=dashboard.description,
            **serialized_dashboard,
        )

    def import_serialized(
        self,
        workspace: Workspace,
        serialized_values: Dict[str, Any],
        import_export_config: ImportExportConfig,
        id_mapping: Dict[str, Any],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Application:
        """
        Imports a dashboard application exported by the `export_serialized` method.
        """

        progress = ChildProgressBuilder.build(progress_builder, child_total=100)

        application = super().import_serialized(
            workspace,
            serialized_values,
            import_export_config,
            id_mapping,
            files_zip,
            storage,
            progress.create_child_builder(represents_progress=100),
        )

        if description := serialized_values.pop("description", ""):
            application.description = description
            application.save()

        return application
