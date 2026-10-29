from zipfile import ZipFile

from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage
from django.db import transaction
from django.db.transaction import Atomic
from django.urls import URLResolver, include, path

from baserow.contrib.agent.api.serializers import AgentApplicationSerializer
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentApplication
from baserow.contrib.agent.operations import ReadAgentConfigurationOperationType
from baserow.contrib.agent.registries import agent_tool_type_registry
from baserow.core.ai_provider.constants import AI_PROVIDER_FEATURE_AI_AGENT
from baserow.core.feature_flags import FF_AGENT_BUILDER, feature_flag_is_enabled
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.registries import ApplicationType, ImportExportConfig
from baserow.core.storage import ExportZipFile
from baserow.core.utils import ChildProgressBuilder


class AgentApplicationType(ApplicationType):
    type = "agent"
    model_class = AgentApplication
    serializer_field_names = ["name", "readiness"]
    serializer_mixins = [AgentApplicationSerializer]
    request_serializer_field_names = ["name"]
    request_serializer_mixins = []

    @staticmethod
    def _includes_conversations(import_export_config: ImportExportConfig) -> bool:
        """Conversations are private, so only internal full-data copies carry them."""

        return (
            import_export_config.is_duplicate
            and not import_export_config.is_template
            and not import_export_config.is_publishing
            and not import_export_config.only_structure
            and not import_export_config.exclude_sensitive_data
        )

    @staticmethod
    def _imported_run_as(
        workspace: Workspace | None,
        serialized_values: dict,
        import_export_config: ImportExportConfig,
    ) -> tuple[str | None, int | None]:
        """
        Keep the identity only in internal copies that stay in its workspace.

        :param workspace: The workspace the Agent is imported into, or None for a
            snapshot, which keeps the identity for its restore.
        :param serialized_values: The exported Agent.
        :param import_export_config: How the Agent is imported.
        :return: The run-as type and id to save.
        """

        run_as = (
            serialized_values.get("run_as_subject_type"),
            serialized_values.get("run_as_subject_id"),
        )
        # Ids from another instance or template could match unrelated identities.
        if not import_export_config.is_duplicate or import_export_config.is_template:
            return None, None
        if workspace is None or AgentHandler().get_usable_run_as_subject(
            *run_as, workspace
        ):
            return run_as
        return None, None

    def get_api_urls(self) -> list[URLResolver]:
        from baserow.contrib.agent.api import urls as api_urls

        return [path("agent/", include(api_urls, namespace=self.type))]

    def export_safe_transaction_context(self, application: AgentApplication) -> Atomic:
        return transaction.atomic()

    def create_application(
        self,
        user: AbstractUser,
        workspace: Workspace,
        init_with_data: bool = False,
        **kwargs,
    ) -> AgentApplication:
        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        models = generative_ai_model_type_registry.get_enabled_models_per_type(
            workspace, feature_type=AI_PROVIDER_FEATURE_AI_AGENT
        )
        # Match AI Agent service defaults, only when creating a new application.
        # Reading or importing an Agent must preserve deliberately blank settings.
        if models and not {"provider_type", "model_identifier"}.intersection(kwargs):
            provider_type, identifiers = next(iter(models.items()))
            kwargs.update(provider_type=provider_type, model_identifier=identifiers[0])
        return super().create_application(
            user, workspace, init_with_data=init_with_data, **kwargs
        )

    def after_create(self, instance: AgentApplication, values: dict) -> None:
        """New Agents start with the tools that only read data."""

        AgentHandler().set_tools(
            instance,
            [
                tool_type.type
                for tool_type in agent_tool_type_registry.get_all()
                if not tool_type.changes_data
            ],
        )

    def export_serialized(
        self,
        application: AgentApplication,
        import_export_config: ImportExportConfig,
        files_zip: ExportZipFile | None = None,
        storage: Storage | None = None,
        progress_builder: ChildProgressBuilder | None = None,
    ) -> dict:
        """Package the configuration, adding conversations only to internal copies."""

        if import_export_config.exported_by is not None:
            CoreHandler().check_permissions(
                import_export_config.exported_by,
                ReadAgentConfigurationOperationType.type,
                workspace=application.workspace,
                context=application,
            )
        serialized = super().export_serialized(
            application, import_export_config, files_zip, storage, progress_builder
        )
        serialized.update(
            instructions=application.instructions,
            provider_type=application.provider_type,
            model_identifier=application.model_identifier,
            run_as_subject_type=application.run_as_subject_type,
            run_as_subject_id=application.run_as_subject_id,
            tools=AgentHandler().get_tool_names(application),
        )
        if self._includes_conversations(import_export_config):
            serialized["conversations"] = AgentHandler().export_conversations(
                application
            )
        return serialized

    def import_serialized(
        self,
        workspace: Workspace | None,
        serialized_values: dict,
        import_export_config: ImportExportConfig,
        id_mapping: dict,
        files_zip: ZipFile | None = None,
        storage: Storage | None = None,
        progress_builder: ChildProgressBuilder | None = None,
    ) -> AgentApplication:
        """Import the configuration and any copied conversations as one new Agent."""

        application = super().import_serialized(
            workspace,
            serialized_values,
            import_export_config,
            id_mapping,
            files_zip,
            storage,
            progress_builder,
        )
        application.instructions = serialized_values.get("instructions", "")
        application.provider_type = serialized_values.get("provider_type") or None
        application.model_identifier = serialized_values.get("model_identifier") or None
        application.run_as_subject_type, application.run_as_subject_id = (
            self._imported_run_as(workspace, serialized_values, import_export_config)
        )
        application.save()
        registered = agent_tool_type_registry.get_types()
        AgentHandler().set_tools(
            application,
            [name for name in serialized_values.get("tools", []) if name in registered],
        )
        if self._includes_conversations(import_export_config):
            AgentHandler().import_conversations(
                application, serialized_values.get("conversations", [])
            )
        return application
