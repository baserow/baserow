from typing import Any, Dict, List, Optional
from zipfile import ZipFile

from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage
from django.db import transaction
from django.db.models import Prefetch, QuerySet
from django.db.transaction import Atomic
from django.urls import include, path

from baserow.contrib.automation.automation_init_application import (
    AutomationApplicationTypeInitApplication,
)
from baserow.contrib.automation.constants import IMPORT_SERIALIZED_IMPORTING
from baserow.contrib.automation.models import Automation, AutomationWorkflow
from baserow.contrib.automation.operations import ListAutomationWorkflowsOperationType
from baserow.contrib.automation.types import AutomationDict
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.core.handler import CoreHandler
from baserow.core.models import Application, Workspace
from baserow.core.registries import ApplicationType, ImportExportConfig
from baserow.core.utils import ChildProgressBuilder


def lazy_get_instance_serializer_class():
    from baserow.contrib.automation.api.serializers import AutomationSerializer

    return AutomationSerializer


class AutomationApplicationType(ApplicationType):
    type = "automation"
    model_class = Automation
    serializer_field_names = [
        "name",
        "workflows",
    ]
    allowed_fields = []
    request_serializer_field_names = []
    serializer_mixins = [lazy_get_instance_serializer_class]

    # Automation applications are imported third (after database, builder)
    import_application_priority = 0

    def get_api_urls(self):
        from .api import urls as api_urls

        return [
            path("automation/", include(api_urls, namespace=self.type)),
        ]

    def export_safe_transaction_context(self, application: Application) -> Atomic:
        return transaction.atomic()

    def init_application(self, user: AbstractUser, application: Application) -> None:
        """
        Responsible for creating default workflows in the newly created
        Automation application.

        :param user: The user that is creating a new automation application.
        :param application: The newly created automation application.
        :return: None
        """

        automation_init = AutomationApplicationTypeInitApplication(user, application)
        automation_init.create_workflow(automation_init.workflow_name)

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

        handler = AutomationWorkflowHandler()
        workflows = handler.get_workflows(automation)

        serialized_workflows = [
            handler.export_workflow(
                w,
                files_zip=files_zip,
                storage=storage,
                cache=self.cache,
            )
            for w in workflows
        ]

        serialized_automation = super().export_serialized(
            automation,
            import_export_config,
            files_zip=files_zip,
            storage=storage,
        )
        return AutomationDict(
            workflows=serialized_workflows,
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

        serialized_workflows = serialized_values.pop("workflows")

        (
            automation_progress,
            workflow_progress,
        ) = (20, 80)
        progress = ChildProgressBuilder.build(
            progress_builder, child_total=automation_progress + workflow_progress
        )

        application = super().import_serialized(
            workspace,
            serialized_values,
            import_export_config,
            id_mapping,
            files_zip,
            storage,
            progress.create_child_builder(represents_progress=100),
        )

        if not serialized_workflows:
            progress.increment(state=IMPORT_SERIALIZED_IMPORTING, by=workflow_progress)
        else:
            AutomationWorkflowHandler().import_workflows(
                application,
                serialized_workflows,
                id_mapping,
                files_zip,
                storage,
                progress.create_child_builder(represents_progress=workflow_progress),
            )

        return application

    def fetch_workflows_to_serialize(
        self, automation: Application, user: AbstractUser | None
    ) -> List[AutomationWorkflow]:
        """
        Serializes the workflows of the automation application, making sure
        that the user has the correct permissions to view them if provided.

        :param automation: The automation application instance.
        :param user: The user trying to access the workflows.
        :return: A list of serialized workflows that belong to this instance.
        """

        base_queryset = Automation.objects.filter(id=automation.id)
        if user:
            instance = self.enhance_and_filter_queryset(
                base_queryset, user, automation.workspace
            ).first()
            return instance and list(instance.workflows.all()) or []
        else:
            instance = self.enhance_queryset(base_queryset).first()
            return instance and list(instance.workflows.all()) or []

    def enhance_queryset(self, queryset):
        return queryset.prefetch_related("workflows")

    def enhance_and_filter_queryset(
        self,
        queryset: QuerySet[Automation],
        user: AbstractUser,
        workspace: Workspace,
    ) -> QuerySet[Automation]:
        return queryset.prefetch_related(
            Prefetch(
                "workflows",
                queryset=CoreHandler().filter_queryset(
                    user,
                    ListAutomationWorkflowsOperationType.type,
                    AutomationWorkflow.objects.select_related(
                        "automation__workspace"
                    ).all(),
                    workspace=workspace,
                ),
            ),
        )
