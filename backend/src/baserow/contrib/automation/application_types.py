from typing import Any, Dict, Optional
from zipfile import ZipFile

from django.core.files.storage import Storage
from django.db import transaction
from django.db.transaction import Atomic
from django.urls import include, path

from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.types import AutomationDict
from baserow.core.models import Application, Workspace
from baserow.core.registries import ApplicationType, ImportExportConfig
from baserow.core.utils import ChildProgressBuilder


class AutomationApplicationType(ApplicationType):
    type = "automation"
    model_class = Automation
    serializer_field_names = [
        "name",
    ]

    def get_api_urls(self):
        from .api import urls as api_urls

        return [
            path("automation/", include(api_urls, namespace=self.type)),
        ]

    def export_safe_transaction_context(self, application: Application) -> Atomic:
        return transaction.atomic()

    def export_serialized(
        self,
        automation: Automation,
        import_export_config: ImportExportConfig,
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress_builder: ChildProgressBuilder | None = None,
    ) -> AutomationDict:
        """
        Exports the automation application type to a serialized format that can later
        be imported via the `import_serialized`.
        """

        self.cache = {}
        serialized_automation = super().export_serialized(
            automation,
            import_export_config,
            files_zip=files_zip,
            storage=storage,
        )
        return AutomationDict(
            **serialized_automation,
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
        Imports an automation application exported by the `export_serialized` method.
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

        return application
