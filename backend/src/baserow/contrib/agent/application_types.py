from uuid import uuid4
from zipfile import ZipFile

from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage
from django.db import transaction
from django.db.transaction import Atomic
from django.urls import URLResolver, include, path
from django.utils.crypto import salted_hmac

from celery.exceptions import SoftTimeLimitExceeded
from loguru import logger
from rest_framework.exceptions import ValidationError

from baserow.api.validators import no_url_validation
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
from baserow.core.exceptions import PermissionException
from baserow.core.feature_flags import FF_AGENT_BUILDER, feature_flag_is_enabled
from baserow.core.generative_ai.constants import ReasoningEffort
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.identities.actions import CreateScopedIdentityActionType
from baserow.core.identities.exceptions import IdentityCannotBeScoped
from baserow.core.identities.registries import identity_extension_type_registry
from baserow.core.identities.service import IdentityService
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.operations import ReadIntegrationOperationType
from baserow.core.models import Workspace
from baserow.core.registries import ApplicationType, ImportExportConfig
from baserow.core.storage import ExportZipFile
from baserow.core.subjects import UserSubjectType
from baserow.core.types import PermissionCheck
from baserow.core.utils import ChildProgressBuilder, exception_capturer


class AgentApplicationType(ApplicationType):
    type = "agent"
    model_class = AgentApplication
    data_provider_type_registry = agent_data_provider_type_registry
    serializer_field_names = ["name", "readiness"]
    serializer_mixins = [AgentApplicationSerializer]
    request_serializer_field_names = ["name"]
    request_serializer_mixins = []
    supports_integrations = True
    # After the applications its identity has roles on, so their ids are mapped.
    import_application_priority = -1

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
    def _serialized_identity(key: str, roles: list | None) -> dict:
        """
        :param key: Says which Agents of one export act as the same identity.
        :param roles: (application id, role uid) pairs, or None.
        :return: The identity as it's exported and kept by an Agent waiting for one.
        """

        return {
            "key": key,
            "application_roles": None
            if roles is None
            else [
                {"application_id": application_id, "role": role_uid}
                for application_id, role_uid in roles
            ],
        }

    @staticmethod
    def _identity_roles(identity: dict) -> list[tuple[int, str]] | None:
        """
        :param identity: An identity made by `_serialized_identity`.
        :return: Its (application id, role uid) pairs, or None without roles.
        """

        roles = identity.get("application_roles")
        if roles is None:
            return None
        return [(role["application_id"], role["role"]) for role in roles]

    def _exported_identity(
        self, application: AgentApplication, import_export_config: ImportExportConfig
    ) -> dict | None:
        """
        The identity the Agent acts as, for an install to make a new one with the
        same access: a key shared by the Agents that act as it, and the roles it
        has on single applications. The roles are None when its access can't be
        exported this way.

        :param application: The exported Agent.
        :param import_export_config: How the Agent is exported.
        :return: The exported identity, or None when the Agent has none.
        """

        if not (application.run_as_subject_type and application.run_as_subject_id):
            # A copy waiting for an identity, like the Agent of a user template,
            # keeps the identity it was imported with, by its own application ids.
            pending = (application.pending_tool_choices or {}).get("identity")
            if pending is None:
                return None
            roles = self._identity_roles(pending)
            user = import_export_config.exported_by
            if roles is not None and user is not None:
                # Left out, the new identity gets no access to their applications.
                roles = (
                    identity_extension_type_registry.filter_readable_application_roles(
                        roles, user, application.workspace
                    )
                )
            return self._serialized_identity(pending["key"], roles)
        resolution = AgentHandler().resolve_run_as_subject(
            application.run_as_subject_type,
            application.run_as_subject_id,
            application.workspace,
        )
        if resolution.status != AgentRunAsState.ACTIVE:
            return None
        roles = identity_extension_type_registry.get_application_roles(
            resolution.subject, import_export_config.exported_by
        )
        # Not its id, which is a local reference. An import replaces the key.
        key = salted_hmac("agent-exported-identity", str(resolution.subject.id))
        return self._serialized_identity(key.hexdigest(), roles)

    def _imported_identity(
        self, serialized_values: dict, id_mapping: dict
    ) -> dict | None:
        """
        The exported identity of the Agent, with its roles on the applications
        imported with it, by their new ids. Its key is replaced by one of this
        import, so Agents share an identity only with those imported with them.
        Roles that aren't an application id and a role uid are left out, so a
        malformed export can't fail the import.

        :param serialized_values: The exported Agent.
        :param id_mapping: The export-to-import id map.
        :return: The identity the Agent waits for, or None when none was exported.
        """

        exported = serialized_values.get("run_as_identity")
        if not isinstance(exported, dict):
            return None
        exported_key = exported.get("key")
        if isinstance(exported_key, str) and exported_key:
            key = id_mapping.setdefault("agent_identity_keys", {}).setdefault(
                exported_key, uuid4().hex
            )
        else:
            key = uuid4().hex
        exported_roles = exported.get("application_roles")
        if exported_roles is None:
            return self._serialized_identity(key, None)
        if not isinstance(exported_roles, list):
            return self._serialized_identity(key, [])
        applications = id_mapping.get("applications", {})
        return self._serialized_identity(
            key,
            [
                (applications[role["application_id"]], role["role"])
                for role in exported_roles
                if isinstance(role, dict)
                and type(role.get("application_id")) is int
                and isinstance(role.get("role"), str)
                and role["application_id"] in applications
            ],
        )

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

    def create_install_identities(
        self,
        user: AbstractUser,
        workspace: Workspace,
        applications: list[AgentApplication],
        installed_applications: list,
    ) -> None:
        """
        Make the installed Agents with pending tool choices act as new identities.
        Agents that acted as the same identity in the template share one, named
        after the first of them, and any other Agent gets its own, named after it.

        A new identity has no workspace access and a role on only the other
        applications of the same install: the roles the template's identity had
        when it was exported, or else the builder role if one of the tools of its
        Agents changes data, and the viewer role otherwise. Without other
        applications, the identity has no access, and the tools are checked
        against that when they run. Binding it turns the pending tools on, as when
        an identity is picked.

        Agents whose identity can't be created, scoped or bound stay installed
        with their pending choices: the identity is a shortcut that the installer
        can still take by hand, so it doesn't fail the install. Each identity is
        done in a savepoint, so a failure never leaves one behind.
        """

        # Without the feature, the installer can't see the Agents or their identities.
        if not feature_flag_is_enabled(FF_AGENT_BUILDER, user=user):
            logger.warning(
                "Not creating identities for the Agents installed in workspace "
                "{} by user {}: the Agent builder isn't enabled for them.",
                workspace.id,
                user.id,
            )
            return
        # The access may have changed since the install was requested.
        if not IdentityService().can_create_scoped_identity(user, workspace):
            logger.warning(
                "Not creating identities for the Agents installed in workspace "
                "{} by user {}: they can't create scoped identities.",
                workspace.id,
                user.id,
            )
            return
        # Not the Agents, so an identity can't change its own configuration.
        scoped_applications = [
            application
            for application in installed_applications
            if not isinstance(application, AgentApplication)
        ]
        # Agents that wait for the same identity, in the order they were installed.
        waiting: dict[str, list[AgentApplication]] = {}
        for agent in applications:
            if not AgentHandler().get_pending_tool_configuration(agent)[
                "allowed_tools"
            ]:
                continue
            identity = agent.pending_tool_choices.get("identity") or {}
            waiting.setdefault(identity.get("key") or f"agent-{agent.id}", []).append(
                agent
            )
        for agents in waiting.values():
            self._create_install_identity(user, workspace, agents, scoped_applications)

    @staticmethod
    def _can_name_an_identity(name: str) -> bool:
        try:
            no_url_validation(name)
        except ValidationError:
            return False
        return True

    def _create_install_identity(
        self,
        user: AbstractUser,
        workspace: Workspace,
        agents: list[AgentApplication],
        applications: list,
    ) -> None:
        """
        Creates the identity that installed Agents wait for and binds it to each of
        them. See `create_install_identities`.

        :param user: The user who installs the template.
        :param workspace: The workspace the template is installed into.
        :param agents: The installed Agents that wait for the same identity.
        :param applications: The installed applications the identity may access.
        """

        agent_ids = [agent.id for agent in agents]
        # Identity names reach emails, so they get the check of the identities API.
        name = next(
            (
                agent.name[:150]
                for agent in agents
                if self._can_name_an_identity(agent.name[:150])
            ),
            None,
        )
        if name is None:
            logger.warning(
                "Not creating the identity of the installed Agents {}: none of "
                "their names can be the name of an identity.",
                agent_ids,
            )
            return
        # Every Agent holds a copy of the roles of the identity they share.
        roles = self._identity_roles(
            agents[0].pending_tool_choices.get("identity") or {}
        )
        handler = AgentHandler()
        try:
            with transaction.atomic():
                identity = action_type_registry.get_by_type(
                    CreateScopedIdentityActionType
                ).do(
                    user,
                    workspace,
                    name=name,
                    applications=applications,
                    can_change_data=any(
                        agent_tool_type_registry.get(tool).changes_data
                        for agent in agents
                        for tool in handler.get_pending_tool_configuration(agent)[
                            "allowed_tools"
                        ]
                    ),
                    roles=roles,
                )
                # Audited, because the Agents get the identity's access.
                for agent in agents:
                    action_type_registry.get_by_type(
                        UpdateAgentConfigurationActionType
                    ).do(
                        user,
                        agent.id,
                        run_as_subject_type=UserSubjectType.type,
                        run_as_subject_id=identity.id,
                    )
        except (PermissionException, IdentityCannotBeScoped) as error:
            # Expected when the installer can't change an application.
            logger.warning(
                "Not creating the identity of the installed Agents {}: {}",
                agent_ids,
                repr(error),
            )
        except SoftTimeLimitExceeded:
            raise
        except Exception as error:
            logger.exception(
                "Could not create the identity of the installed Agents {}.", agent_ids
            )
            exception_capturer(error)

    def supports_integration_type(self, integration_type) -> bool:
        """MCP servers, and the integrations its action types' services use."""

        from baserow.contrib.integrations.mcp.integration_types import (
            MCPServerIntegrationType,
        )

        return super().supports_integration_type(integration_type) and (
            integration_type.type == MCPServerIntegrationType.type
            or any(
                action_type.service_type.integration_type == integration_type.type
                for action_type in agent_action_type_registry.get_all()
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
            )
        else:
            identity = self._exported_identity(application, import_export_config)
            if identity is not None:
                serialized["run_as_identity"] = identity
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
        if application.run_as_subject_type and application.run_as_subject_id:
            handler.set_allowed_tools(
                application, tools["allowed_tools"], tools["ask_first_tools"]
            )
        elif tools["allowed_tools"]:
            # Without an identity tools are off. They wait for the first one, and
            # those that change data ask first: whoever picks the identity didn't
            # choose to let them run unattended.
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
            identity = self._imported_identity(serialized_values, id_mapping)
            if identity is not None:
                application.pending_tool_choices["identity"] = identity
            application.save(update_fields=["pending_tool_choices"])
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
        return application
