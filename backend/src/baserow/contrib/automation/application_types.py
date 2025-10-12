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
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
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
    supports_integrations = True
    request_serializer_field_names = []
    serializer_mixins = [lazy_get_instance_serializer_class]

    # Automation applications are imported third (after database, builder)
    import_application_priority = 0

    def get_api_urls(self):
        from .api import urls as api_urls

        return [
            path("automation/", include(api_urls, namespace=self.type)),
        ]

    def export_safe_transaction_context(self, application: Automation) -> Atomic:
        return transaction.atomic()

    def init_application(self, user: AbstractUser, application: Automation) -> None:
        """
        Responsible for creating an initial workflow, and Local Baserow integration,
        in the newly created Automation application.

        :param user: The user that is creating a new automation application.
        :param application: The newly created automation application.
        :return: None
        """

        automation_init = AutomationApplicationTypeInitApplication(user, application)
        automation_init.create_workflow(automation_init.workflow_name)
        automation_init.create_local_baserow_integration()

    def export_serialized(
        self,
        automation: Automation,
        import_export_config: ImportExportConfig,
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress_builder: ChildProgressBuilder | None = None,
        workflows: Optional[List[AutomationWorkflow]] = None,
    ) -> AutomationDict:
        """
        Exports the automation application type to a serialized format that can later
        be imported via the `import_serialized`.
        """

        self.cache = {}

        handler = AutomationWorkflowHandler()
        workflows = (
            workflows if workflows is not None else handler.get_workflows(automation)
        )

        serialized_integrations = [
            IntegrationHandler().export_integration(
                i,
                import_export_config,
                files_zip=files_zip,
                storage=storage,
                cache=self.cache,
            )
            for i in IntegrationHandler().get_integrations(automation)
        ]

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
            integrations=serialized_integrations,
            **serialized_automation,
        )

    def import_integrations_serialized(
        self,
        automation: Automation,
        serialized_integrations: List[Dict[str, Any]],
        id_mapping: Dict[str, Any],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> List[Integration]:
        """
        Import integrations to builder. This method has to be compatible with the output
        of `export_integrations_serialized`.

        :param automation: The automation application instance to which the
            integrations should be imported.
        :param serialized_integrations: The integrations that are supposed to be
            imported.
        :param progress_builder: A progress builder that allows for publishing progress.
        :param files_zip: An optional zip file for the related files.
        :param storage: The storage instance.
        :return: The created integration instances.
        """

        progress = ChildProgressBuilder.build(
            progress_builder, child_total=len(serialized_integrations)
        )

        imported_integrations: List[Integration] = []

        for serialized_integration in serialized_integrations:
            integration = IntegrationHandler().import_integration(
                automation,
                serialized_integration,
                id_mapping,
                cache=self.cache,
                files_zip=files_zip,
                storage=storage,
            )
            imported_integrations.append(integration)

            progress.increment(state=IMPORT_SERIALIZED_IMPORTING)

        return imported_integrations

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

        self.cache = {}

        serialized_workflows = serialized_values.pop("workflows")
        serialized_integrations = serialized_values.pop("integrations")

        (
            automation_progress,
            integration_progress,
            workflow_progress,
        ) = (20, 50, 80)
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
        automation = application.specific

        if not serialized_integrations:
            progress.increment(
                state=IMPORT_SERIALIZED_IMPORTING, by=integration_progress
            )
        else:
            self.import_integrations_serialized(
                automation,
                serialized_integrations,
                id_mapping,
                files_zip,
                storage,
                progress.create_child_builder(represents_progress=integration_progress),
            )

        if not serialized_workflows:
            progress.increment(state=IMPORT_SERIALIZED_IMPORTING, by=workflow_progress)
        else:
            AutomationWorkflowHandler().import_workflows(
                automation,
                serialized_workflows,
                id_mapping,
                files_zip,
                storage,
                progress.create_child_builder(represents_progress=workflow_progress),
                import_export_config=import_export_config,
            )

        return automation

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
