from zipfile import ZipFile

from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage
from django.db import transaction
from django.db.transaction import Atomic
from django.urls import URLResolver, include, path

from baserow.contrib.agent.action_tools.handler import AgentActionHandler
from baserow.contrib.agent.action_tools.registries import agent_action_type_registry
from baserow.contrib.agent.actions import UpdateAgentConfigurationActionType
from baserow.contrib.agent.api.serializers import AgentApplicationSerializer
from baserow.contrib.agent.constants import AgentRunAsState
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentApplication
from baserow.contrib.agent.operations import (
    CreateAgentMessageOperationType,
    ReadAgentConfigurationOperationType,
)
from baserow.contrib.agent.registries import (
    agent_data_provider_type_registry,
    agent_tool_type_registry,
)
from baserow.contrib.agent.triggers.handler import AgentTriggerHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.ai_provider.constants import AI_PROVIDER_FEATURE_AI_AGENT
from baserow.core.feature_flags import FF_AGENT_BUILDER, feature_flag_is_enabled
from baserow.core.generative_ai.constants import ReasoningEffort
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.identities.import_export import (
    identity_importer,
    imported_identity,
    imported_identity_definition,
)
from baserow.core.identities.service import IdentityService
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.operations import ReadIntegrationOperationType
from baserow.core.models import IdentityDefinition, Workspace
from baserow.core.registries import ApplicationType, ImportExportConfig
from baserow.core.storage import ExportZipFile
from baserow.core.subjects import UserSubjectType
from baserow.core.types import PermissionCheck
from baserow.core.utils import ChildProgressBuilder


class AgentApplicationType(ApplicationType):
    type = "agent"
    model_class = AgentApplication
    data_provider_type_registry = agent_data_provider_type_registry
    serializer_field_names = ["name", "readiness", "waits_for_identity"]
    serializer_mixins = [AgentApplicationSerializer]
    request_serializer_field_names = ["name"]
    request_serializer_mixins = []
    supports_integrations = True

    @staticmethod
    def _includes_conversations(import_export_config: ImportExportConfig) -> bool:
        """Conversations can quote private data: only full-data duplicates copy them."""

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
        Keep existing identity references in internal copies of their workspace,
        when the person copying or restoring may bind identities.

        A trashed identity remains configured so restoring it also restores access
        for the copy. Execution still requires an active identity.

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
        if workspace is None:
            return run_as
        if not IdentityService().can_copy_binding(workspace, import_export_config):
            return None, None
        resolution = AgentHandler().resolve_run_as_subject(*run_as, workspace)
        if resolution.status in {AgentRunAsState.ACTIVE, AgentRunAsState.TRASHED}:
            return run_as
        return None, None

    @staticmethod
    def _exported_identity_key(
        application: AgentApplication, import_export_config: ImportExportConfig
    ) -> str | None:
        """
        Records the identity the Agent acts as, or the one it waits for, with the
        identities of the export, so that an import can create it again.

        :param application: The exported Agent.
        :param import_export_config: How the Agent is exported.
        :return: The key of the identity in the export, or None when the Agent has
            none or the export carries no identities.
        """

        identity_export = import_export_config.identity_export
        if identity_export is None:
            return None
        if not (application.run_as_subject_type and application.run_as_subject_id):
            # A copy waiting for an identity, like the Agent of a user template.
            definition = application.identity_definition
            return None if definition is None else identity_export.key_for(definition)
        resolution = AgentHandler().resolve_run_as_subject(
            application.run_as_subject_type,
            application.run_as_subject_id,
            application.workspace,
        )
        if resolution.status != AgentRunAsState.ACTIVE:
            return None
        return identity_export.key_for(resolution.subject)

    @staticmethod
    def _enabled_models(workspace: Workspace) -> dict[str, list[str]]:
        return generative_ai_model_type_registry.get_enabled_models_per_type(
            workspace, feature_type=AI_PROVIDER_FEATURE_AI_AGENT
        )

    @staticmethod
    def _default_model(
        enabled_models: dict[str, list[str]],
    ) -> tuple[str | None, str | None]:
        """The first enabled model, like the AI Agent service defaults to."""

        for provider_type, identifiers in enabled_models.items():
            if identifiers:
                return provider_type, identifiers[0]
        return None, None

    def _imported_model(
        self,
        workspace: Workspace | None,
        serialized_values: dict,
        import_export_config: ImportExportConfig,
    ) -> tuple[str | None, str | None]:
        """
        The model an imported Agent replies with: the author's when it's enabled
        in the destination, otherwise the first enabled one. Internal copies and
        template content keep the author's, and so does an import into a workspace
        where nothing is enabled, so its settings show what the author used.

        :param workspace: The workspace the Agent is imported into.
        :param serialized_values: The exported Agent.
        :param import_export_config: How the Agent is imported.
        :return: The provider type and model identifier to save.
        """

        author_model = (
            serialized_values.get("provider_type") or None,
            serialized_values.get("model_identifier") or None,
        )
        if (
            workspace is None
            or import_export_config.keeps_unmapped_references
            or import_export_config.is_template_storage
        ):
            return author_model
        enabled = self._enabled_models(workspace)
        provider_type, model_identifier = author_model
        if model_identifier in enabled.get(provider_type, []):
            return author_model
        default = self._default_model(enabled)
        return default if default[0] else author_model

    def get_imported_identity_keys(
        self, serialized_values: dict, imported_by: AbstractUser | None
    ) -> set[str]:
        key = serialized_values.get("run_as_identity_key")
        if not (isinstance(key, str) and key):
            return set()
        # Without the feature, the user can't see the Agents or their identities.
        if imported_by is not None and not feature_flag_is_enabled(
            FF_AGENT_BUILDER, user=imported_by
        ):
            return set()
        return {key}

    @staticmethod
    def _act_as_imported_identity(
        application: AgentApplication, identity: AbstractUser, id_mapping: dict
    ) -> None:
        """
        Makes an imported Agent act as the identity the import created for it,
        which turns its pending tools on, as when an identity is picked. Audited,
        because the Agent gets the identity's access.

        :param application: The imported Agent, which has no identity yet.
        :param identity: The identity the import created.
        :param id_mapping: The export-to-import id map.
        """

        action_type_registry.get_by_type(UpdateAgentConfigurationActionType).do(
            identity_importer(id_mapping),
            application.id,
            run_as_subject_type=UserSubjectType.type,
            run_as_subject_id=identity.id,
        )
        application.refresh_from_db()

    def supports_integration_type(self, integration_type) -> bool:
        """
        MCP servers, and the integrations its action types' services use. A type
        that acts as the Agent's run identity uses none.
        """

        from baserow.contrib.integrations.mcp.integration_types import (
            MCPServerIntegrationType,
        )

        return super().supports_integration_type(integration_type) and (
            integration_type.type == MCPServerIntegrationType.type
            or any(
                action_type.service_type.integration_type == integration_type.type
                for action_type in agent_action_type_registry.get_all()
                if not action_type.acts_as_run_identity
            )
        )

    def get_api_urls(self) -> list[URLResolver]:
        from baserow.contrib.agent.api import urls as api_urls

        return [path("agent/", include(api_urls, namespace=self.type))]

    def get_pending_counts(
        self, users: list[AbstractUser], applications: list[AgentApplication]
    ) -> dict[int, dict[int, int]]:
        """
        Count the held calls waiting for each user's decision: in their own
        conversations with each Agent, and in its shared ones when they may send
        it messages.

        :param users: The users to count for.
        :param applications: The Agents to count in.
        :return: The number of pending approvals by Agent id, by user id, leaving
            out users and Agents with none.
        """

        handler = AgentHandler()
        agent_ids = [application.id for application in applications]
        counts = handler.get_pending_approval_counts(
            [user.id for user in users], agent_ids
        )
        shared_counts = handler.get_shared_pending_approval_counts(agent_ids)
        for application in applications:
            if application.id not in shared_counts:
                continue
            for user in CoreHandler().check_permission_for_multiple_actors(
                users,
                CreateAgentMessageOperationType.type,
                application.workspace,
                context=application,
            ):
                user_counts = counts.setdefault(user.id, {})
                user_counts[application.id] = (
                    user_counts.get(application.id, 0) + shared_counts[application.id]
                )
        return counts

    def export_safe_transaction_context(self, application: AgentApplication) -> Atomic:
        return transaction.atomic()

    def create_application(
        self,
        user: AbstractUser,
        workspace: Workspace,
        init_with_data: bool = False,
        **kwargs,
    ) -> AgentApplication:
        # Match AI Agent service defaults when no model is given. An import picks
        # its model in `_imported_model`, which also fills a blank one.
        if not {"provider_type", "model_identifier"}.intersection(kwargs):
            provider_type, model_identifier = self._default_model(
                self._enabled_models(workspace)
            )
            if provider_type:
                kwargs.update(
                    provider_type=provider_type, model_identifier=model_identifier
                )
        return super().create_application(
            user, workspace, init_with_data=init_with_data, **kwargs
        )

    def _integrations_to_export(
        self, application: AgentApplication, import_export_config: ImportExportConfig
    ) -> list[Integration]:
        """
        The connected apps a copy carries. A duplicate keeps their credentials,
        so it only carries the ones the person copying may read.
        """

        integrations = list(IntegrationHandler().get_integrations(application))
        copied_by = import_export_config.copied_by
        if copied_by is None or import_export_config.exclude_sensitive_data:
            return integrations
        checks = [
            PermissionCheck(copied_by, ReadIntegrationOperationType.type, integration)
            for integration in integrations
        ]
        allowed = CoreHandler().check_multiple_permissions(
            checks, workspace=application.workspace
        )
        return [
            integration
            for check, integration in zip(checks, integrations)
            if allowed.get(check, False) is True
        ]

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
            reasoning_effort=application.reasoning_effort,
            **AgentHandler().get_exported_tool_configuration(application),
            integrations=[
                IntegrationHandler().export_integration(
                    integration,
                    import_export_config=import_export_config,
                    files_zip=files_zip,
                    storage=storage,
                )
                for integration in self._integrations_to_export(
                    application, import_export_config
                )
            ],
            web_search_enabled=application.web_search_enabled,
            web_fetch_enabled=application.web_fetch_enabled,
            actions=AgentActionHandler().export_actions(
                application, import_export_config, files_zip, storage
            ),
            triggers=AgentTriggerHandler().export_triggers(
                application, import_export_config, files_zip, storage
            ),
        )
        # Identity ids are local references, not portable configuration.
        if (
            import_export_config.is_duplicate
            and not import_export_config.is_template
            and not import_export_config.exclude_sensitive_data
        ):
            serialized.update(
                run_as_subject_type=application.run_as_subject_type,
                run_as_subject_id=application.run_as_subject_id,
                # A copy of an Agent waiting for an identity waits for it too.
                identity_definition_id=application.identity_definition_id,
            )
        else:
            key = self._exported_identity_key(application, import_export_config)
            if key is not None:
                serialized["run_as_identity_key"] = key
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
        """
        Import the configuration, its triggers switched off, and any copied
        conversations as one new Agent.

        :param workspace: The workspace the Agent is imported into.
        :param serialized_values: The exported Agent.
        :param import_export_config: How the Agent is imported.
        :param id_mapping: The export-to-import id map, filled in.
        :param files_zip: The zip file service files are read from.
        :param storage: The storage service files are written to.
        :param progress_builder: Reports the import's progress.
        :return: The new Agent.
        """

        serialized_integrations = serialized_values.pop("integrations", [])
        id_mapping.setdefault("integrations", {})
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
        application.provider_type, application.model_identifier = self._imported_model(
            workspace, serialized_values, import_export_config
        )
        reasoning_effort = serialized_values.get("reasoning_effort")
        application.reasoning_effort = (
            reasoning_effort if reasoning_effort in ReasoningEffort else None
        )
        application.run_as_subject_type, application.run_as_subject_id = (
            self._imported_run_as(workspace, serialized_values, import_export_config)
        )
        # Searching is paid, and both send data out, so outside copies must opt in
        # again.
        internal_copy = (
            import_export_config.is_duplicate and not import_export_config.is_template
        )
        application.web_search_enabled = internal_copy and serialized_values.get(
            "web_search_enabled", False
        )
        application.web_fetch_enabled = internal_copy and serialized_values.get(
            "web_fetch_enabled", False
        )
        application.save()
        handler = AgentHandler()
        tools = handler.filter_tool_choices(
            serialized_values.get("allowed_tools") or [],
            serialized_values.get("ask_first_tools") or [],
        )
        key = serialized_values.get("run_as_identity_key")
        identity = imported_identity(id_mapping, key)
        if application.run_as_subject_type and application.run_as_subject_id:
            handler.set_allowed_tools(
                application, tools["allowed_tools"], tools["ask_first_tools"]
            )
        else:
            if tools["allowed_tools"]:
                # Without an identity tools are off. They wait for the first one,
                # and those that change data ask first: whoever picks the identity
                # didn't choose to let them run unattended.
                application.pending_tool_choices = handler.filter_tool_choices(
                    tools["allowed_tools"],
                    [
                        *tools["ask_first_tools"],
                        *(
                            name
                            for name in tools["allowed_tools"]
                            if agent_tool_type_registry.get(name).changes_data
                        ),
                    ],
                )
            if import_export_config.keeps_unmapped_references:
                # An internal copy waits for the same identity as its original. A
                # snapshot has no workspace, and keeps it for its restore.
                definitions = IdentityDefinition.objects.filter(
                    id=serialized_values.get("identity_definition_id")
                )
                if workspace is not None:
                    definitions = definitions.filter(workspace=workspace)
                application.identity_definition = definitions.first()
            elif identity is None:
                # The identity the Agent came with, when the export carries it
                # and the import didn't create it.
                application.identity_definition = imported_identity_definition(
                    id_mapping, key
                )
            application.save(
                update_fields=["pending_tool_choices", "identity_definition"]
            )
        for serialized_integration in serialized_integrations:
            IntegrationHandler().import_integration(
                application,
                serialized_integration,
                id_mapping,
                files_zip=files_zip,
                storage=storage,
                import_export_config=import_export_config,
            )
        AgentActionHandler().import_actions(
            application,
            serialized_values.get("actions", []),
            id_mapping,
            import_export_config,
            files_zip,
            storage,
        )
        AgentTriggerHandler().import_triggers(
            application,
            serialized_values.get("triggers", []),
            id_mapping,
            import_export_config,
            files_zip,
            storage,
        )
        if self._includes_conversations(import_export_config):
            AgentHandler().import_conversations(
                application, serialized_values.get("conversations", []), id_mapping
            )
        if identity is not None and not application.run_as_subject_id:
            self._act_as_imported_identity(application, identity, id_mapping)
        return application
