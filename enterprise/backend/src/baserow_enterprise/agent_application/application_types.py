from typing import cast

from django.core.files.storage import Storage
from django.db import transaction
from django.db.transaction import Atomic
from django.urls import include, path
from django.utils import translation
from django.utils.translation import gettext as _

from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.integrations.local_baserow.integration_types import (
    LocalBaserowIntegrationType,
)
from baserow.core.agents.exceptions import AgentDoesNotExist
from baserow.core.agents.handler import AgentHandler
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.models import Agent, Application, Workspace
from baserow.core.registries import ApplicationType, ImportExportConfig
from baserow.core.services.handler import ServiceHandler
from baserow.core.skills.models import WorkspaceSkill
from baserow.core.storage import ExportZipFile
from baserow.core.utils import ChildProgressBuilder

from .channels.registries import agent_chat_channel_type_registry
from .handler import AgentApplicationHandler
from .models import (
    AgentApplication,
    AgentChat,
    AgentChatChannel,
    AgentChatMessage,
    AgentChatToolApproval,
    AgentDefinition,
    AgentSkill,
    AgentTool,
    AgentTrigger,
)
from .types import AgentApplicationDict


class PendingApprovalsCountField(serializers.Field):
    """
    The number of tool calls waiting in the application's approval queue,
    read from the queryset annotation when present (workspace application
    listing) and computed otherwise.
    """

    def __init__(self, **kwargs):
        kwargs["source"] = "*"
        kwargs["read_only"] = True
        super().__init__(**kwargs)

    def to_representation(self, instance):
        # During create validation the polymorphic serializer maps the raw
        # request dict through this field; only a persisted application can
        # have pending approvals.
        if not isinstance(instance, Application):
            return 0

        count = getattr(instance, "pending_approvals_count", None)
        if count is None:
            from .handler import AgentChatHandler

            count = AgentChatHandler().get_pending_approvals_count(instance)
        return count


class LastRunOnField(serializers.DateTimeField):
    """
    When the application's last triggered run finished, read from the
    queryset annotation when present and computed otherwise.
    """

    def __init__(self, **kwargs):
        kwargs["source"] = "*"
        kwargs["read_only"] = True
        super().__init__(**kwargs)

    def to_representation(self, instance):
        if not isinstance(instance, Application):
            return None

        if hasattr(instance, "last_run_on"):
            value = instance.last_run_on
        else:
            from .handler import AgentChatHandler

            value = AgentChatHandler().get_last_run_on(instance)
        return super().to_representation(value) if value else None


SETUP_FIELDS = [
    "instructions",
    "run_mode",
    "trigger_table_id",
    "actions",
    "permissions",
    "web_search",
    "create_identity",
    "skills",
]
RUN_MODES = [
    "chat",
    "daily",
    "weekly",
    "rows_created",
    "rows_updated",
    "rows_deleted",
    "row_comment_created",
]
# Action tools a template may add; the service is created unconfigured.
SETUP_ACTIONS = ["smtp_email", "slack_write_message"]
PERMISSION_PRESETS = ["read_only", "ask_first", "free"]


class AgentApplicationType(ApplicationType):
    type = "agent"
    model_class = AgentApplication
    serializer_field_names = [
        "name",
        "description",
        "active",
        "agent_identity_id",
        "pending_approvals_count",
        "last_run_on",
    ]
    # The wizard's setup choices are accepted on create only (the view injects
    # the serialized data, which drops write-only fields, so they live on the
    # request serializer instead).
    request_serializer_field_names = [*serializer_field_names, *SETUP_FIELDS]
    allowed_fields = ["description", "active", "agent_identity_id", *SETUP_FIELDS]
    serializer_field_overrides = {
        "agent_identity_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            help_text=(
                "The workspace agent subject this application acts as within "
                "the workspace."
            ),
        ),
        "pending_approvals_count": PendingApprovalsCountField(),
        "last_run_on": LastRunOnField(),
    }
    request_serializer_field_overrides = {
        **serializer_field_overrides,
        "instructions": serializers.CharField(
            required=False,
            allow_blank=True,
            help_text="Initial instructions of the agent (create only).",
        ),
        "run_mode": serializers.ChoiceField(
            choices=RUN_MODES,
            required=False,
            help_text=(
                "Adds a periodic or table trigger when not `chat` (create only)."
            ),
        ),
        "trigger_table_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            help_text="The table of a table trigger `run_mode` (create only).",
        ),
        "actions": serializers.ListField(
            child=serializers.ChoiceField(choices=SETUP_ACTIONS),
            required=False,
            help_text="Action tools to add, by service type (create only).",
        ),
        "permissions": serializers.ChoiceField(
            choices=PERMISSION_PRESETS,
            required=False,
            help_text="Workspace tool access preset (create only).",
        ),
        "web_search": serializers.BooleanField(
            required=False,
            help_text="Whether to enable the web search tool (create only).",
        ),
        "create_identity": serializers.BooleanField(
            required=False,
            help_text=(
                "Creates a workspace agent identity named after the application "
                "and acts as it (create only, requires the create agent permission)."
            ),
        ),
        "skills": serializers.ListField(
            child=serializers.DictField(),
            required=False,
            help_text=(
                "Workspace skills the agent follows, as `{skill_id, mode}` "
                "entries with mode `always` or `on_demand` (create only)."
            ),
        ),
    }
    supports_integrations = True

    def get_api_urls(self):
        from baserow_enterprise.api.agent_application import urls as api_urls

        return [
            path("agent_application/", include(api_urls, namespace=self.type)),
        ]

    def export_safe_transaction_context(self, application: Application) -> Atomic:
        return transaction.atomic()

    def pre_delete(self, application: Application) -> None:
        """
        Deletes the trigger and tool services through their handlers before
        the application cascade runs, so every service type's `before_delete`
        hook fires (periodic schedules, public webhook uids, inbound email
        addresses) and no orphaned service rows are left behind.
        """

        from .tools.handler import AgentToolHandler
        from .triggers.handler import AgentTriggerHandler

        for trigger in AgentTrigger.objects_and_trash.filter(
            application_id=application.id
        ).select_related("service"):
            AgentTriggerHandler().delete_trigger(trigger)
        for tool in AgentTool.objects_and_trash.filter(
            agent__application_id=application.id
        ).select_related("service"):
            AgentToolHandler().delete_tool(tool)

    def prepare_value_for_db(
        self, values: dict, instance: "Application | None" = None
    ) -> dict:
        if instance is not None:
            # The setup choices only make sense while creating.
            for field in SETUP_FIELDS:
                values.pop(field, None)

        if "agent_identity_id" in values:
            agent_identity_id = values["agent_identity_id"]

            if instance is None:
                # At creation time there is no workspace to validate the agent
                # against yet; `apply_setup` validates it after creation.
                return values

            if agent_identity_id is not None:
                try:
                    AgentHandler().get_agent(
                        agent_identity_id,
                        base_queryset=Agent.objects.filter(
                            workspace_id=instance.workspace_id
                        ),
                    )
                except AgentDoesNotExist as exc:
                    raise DRFValidationError(
                        detail=f"The agent with ID {agent_identity_id} does not "
                        "exist in the application's workspace.",
                        code="invalid_agent",
                    ) from exc

        # The prepared values stay `agent_identity_id` (not the model
        # instance) because the update action serializes them for undo/redo.
        return values

    def create_application(self, user, workspace, init_with_data=False, **kwargs):
        setup = {key: kwargs.pop(key) for key in SETUP_FIELDS if key in kwargs}
        agent_identity_id = kwargs.pop("agent_identity_id", None)
        application = super().create_application(
            user, workspace, init_with_data=init_with_data, **kwargs
        )
        AgentApplicationHandler().apply_setup(
            user, application, setup, agent_identity_id=agent_identity_id
        )
        return application

    def after_update(self, instance: "Application", values: dict, **kwargs) -> None:
        if "agent_identity_id" in values:
            AgentApplicationHandler().sync_agent_identity(instance.specific)

    def init_application(self, user, application: "Application") -> None:
        with translation.override(user.profile.language):
            integration_name = _("Local Baserow")

        application = application.specific
        IntegrationHandler().create_integration(
            integration_type=integration_type_registry.get(
                LocalBaserowIntegrationType.type
            ),
            application=application,
            authorized_user=user,
            name=integration_name,
        )
        AgentApplicationHandler().create_main_agent(
            application, name=application.name, description=application.description
        )

    def _export_tool_config(
        self, tool: AgentTool, import_export_config: ImportExportConfig
    ) -> dict:
        """
        A tool config can hold workspace subject ids (which identity runs a
        workspace tool) and credentials (MCP headers). Both only make sense
        for a duplicate within the same workspace; anything leaving the
        workspace gets them stripped.
        """

        config = dict(tool.config or {})
        if import_export_config.is_duplicate:
            return config
        config.pop("tool_identities", None)
        if tool.type == "mcp" and config.get("headers"):
            config["headers"] = {}
        return config

    def _export_example_chats(
        self, agent: AgentDefinition, import_export_config: ImportExportConfig
    ) -> list[dict]:
        """
        Pinned manual conversations travel along with exports and templates as
        example conversations, so a template can show what talking to the
        agent looks like. A duplicate copies configuration only, so it skips
        them. Only what a reader needs is exported: the messages, never the
        model history, the author, approvals or token counts.
        """

        if import_export_config.is_duplicate:
            return []
        chats = (
            AgentChat.objects.filter(
                agent=agent, pinned=True, source=AgentChat.Source.MANUAL
            )
            .exclude(status=AgentChat.Status.IN_PROGRESS)
            .order_by("id")
            .prefetch_related("messages")
        )
        return [
            {
                "title": chat.title,
                "messages": [
                    {
                        "role": message.role,
                        "content": message.content,
                        "artifacts": message.artifacts,
                    }
                    for message in chat.messages.order_by("id")
                    if message.role
                    in (AgentChatMessage.Role.HUMAN, AgentChatMessage.Role.AI)
                ],
            }
            for chat in chats
        ]

    def export_serialized(
        self,
        agent_application: AgentApplication,
        import_export_config: ImportExportConfig,
        files_zip: ExportZipFile | None = None,
        storage: Storage | None = None,
        progress_builder: ChildProgressBuilder | None = None,
    ) -> AgentApplicationDict:
        self.cache = {}

        serialized_integrations = [
            IntegrationHandler().export_integration(
                i,
                files_zip=files_zip,
                storage=storage,
                cache=self.cache,
                import_export_config=import_export_config,
            )
            for i in IntegrationHandler().get_integrations(agent_application)
        ]
        is_duplicate = import_export_config.is_duplicate

        serialized_agents = [
            {
                "id": agent.id,
                "name": agent.name,
                "description": agent.description,
                "instructions": agent.instructions,
                "memory": agent.memory,
                "ai_generative_ai_type": agent.ai_generative_ai_type,
                "ai_generative_ai_model": agent.ai_generative_ai_model,
                "ai_temperature": agent.ai_temperature,
                "example_chats": self._export_example_chats(
                    agent, import_export_config
                ),
                # Skills are workspace level, so the links only survive a
                # duplicate within the same workspace.
                "skills": (
                    [
                        {"skill_id": agent_skill.skill_id, "mode": agent_skill.mode}
                        for agent_skill in agent.agent_skills.order_by("order", "id")
                    ]
                    if import_export_config.is_duplicate
                    else []
                ),
            }
            for agent in agent_application.agents.all()
        ]

        serialized_triggers = [
            {
                "id": trigger.id,
                "enabled": trigger.enabled,
                "service": ServiceHandler().export_service(
                    trigger.service.specific,
                    files_zip=files_zip,
                    storage=storage,
                    cache=self.cache,
                ),
            }
            for trigger in AgentTrigger.objects.filter(
                application=agent_application
            ).select_related("service")
        ]

        serialized_tools = [
            {
                "id": tool.id,
                "type": tool.type,
                "name": tool.name,
                "config": self._export_tool_config(tool, import_export_config),
                "order": tool.order,
                # The identity is a workspace level subject, like the
                # application's own identity below.
                "identity_id": tool.identity_id if is_duplicate else None,
                "service": (
                    ServiceHandler().export_service(
                        tool.service.specific,
                        files_zip=files_zip,
                        storage=storage,
                        cache=self.cache,
                    )
                    if tool.service_id is not None
                    else None
                ),
            }
            for tool in AgentTool.objects.filter(
                agent__application=agent_application
            ).select_related("service")
        ]

        # Chat channel configs contain external credentials (e.g. Slack
        # tokens), so they only survive a duplicate within the same
        # workspace; templates and snapshots must never carry them.
        serialized_channels = (
            [
                {
                    "id": channel.id,
                    "type": channel.type,
                    "name": channel.name,
                    "config": channel.config,
                    "enabled": channel.enabled,
                }
                for channel in AgentChatChannel.objects.filter(
                    application=agent_application
                )
            ]
            if import_export_config.is_duplicate
            else []
        )

        serialized_application = super().export_serialized(
            agent_application,
            import_export_config,
            files_zip=files_zip,
            storage=storage,
            progress_builder=progress_builder,
        )

        return AgentApplicationDict(
            description=agent_application.description,
            # The identity is a workspace level subject, so it only survives a
            # duplicate within the same workspace; templates and snapshots
            # must never carry it.
            agent_identity_id=(
                agent_application.agent_identity_id
                if import_export_config.is_duplicate
                else None
            ),
            integrations=serialized_integrations,
            agents=serialized_agents,
            triggers=serialized_triggers,
            tools=serialized_tools,
            chat_channels=serialized_channels,
            **serialized_application,
        )

    def _importable_model(
        self,
        workspace: Workspace,
        serialized_agent: dict,
        import_export_config: ImportExportConfig,
    ) -> dict:
        """
        A template author's model is replaced by the workspace's default when
        this workspace cannot use it, so an installed agent runs out of the
        box. Duplicates and exported applications keep the model as is.
        """

        from baserow.core.ai_provider.constants import (
            AI_PROVIDER_FEATURE_AGENT_BUILDER,
        )
        from baserow.core.generative_ai.registries import (
            generative_ai_model_type_registry,
        )

        exported = {
            "ai_generative_ai_type": serialized_agent.get("ai_generative_ai_type"),
            "ai_generative_ai_model": serialized_agent.get("ai_generative_ai_model"),
        }
        if not import_export_config.is_template:
            return exported
        ai_type, ai_model = exported.values()
        enabled = generative_ai_model_type_registry.get_enabled_models_per_type(
            workspace, feature_type=AI_PROVIDER_FEATURE_AGENT_BUILDER
        )
        if ai_type and ai_model in enabled.get(ai_type, []):
            return exported
        default = AgentApplicationHandler().pick_default_model(workspace)
        if default is None:
            return exported
        return {
            "ai_generative_ai_type": default[0],
            "ai_generative_ai_model": default[1],
        }

    def _import_example_chats(self, agent: AgentDefinition, serialized_chats: list):
        """
        Example conversations come back as finished, ownerless conversations
        without model history: readable in the history, and continuing one
        simply starts the model fresh from the visible messages.
        """

        for serialized_chat in serialized_chats:
            chat = AgentChat.objects.create(
                agent=agent,
                title=(serialized_chat.get("title") or "")[
                    : AgentChat.TITLE_MAX_LENGTH
                ],
                source=AgentChat.Source.MANUAL,
                status=AgentChat.Status.IDLE,
                pinned=True,
            )
            AgentChatMessage.objects.bulk_create(
                [
                    AgentChatMessage(
                        chat=chat,
                        role=message["role"],
                        content=message.get("content", ""),
                        artifacts=message.get("artifacts") or {},
                    )
                    for message in serialized_chat.get("messages", [])
                    if message.get("role")
                    in (AgentChatMessage.Role.HUMAN, AgentChatMessage.Role.AI)
                ]
            )

    def import_serialized(
        self,
        workspace: Workspace,
        serialized_values: dict,
        import_export_config: ImportExportConfig,
        id_mapping: dict,
        files_zip: ExportZipFile | None = None,
        storage: Storage | None = None,
        cache: dict | None = None,
        progress_builder: ChildProgressBuilder | None = None,
    ) -> Application:
        self.cache = {}
        serialized_integrations = serialized_values.pop("integrations", [])
        serialized_agents = serialized_values.pop("agents", [])
        serialized_triggers = serialized_values.pop("triggers", [])
        serialized_tools = serialized_values.pop("tools", [])
        serialized_channels = serialized_values.pop("chat_channels", [])
        description = serialized_values.pop("description", "")
        agent_identity_id = serialized_values.pop("agent_identity_id", None)

        progress = ChildProgressBuilder.build(progress_builder, child_total=100)
        application_progress = progress.create_child_builder(represents_progress=40)
        children_progress = progress.create_child(
            represents_progress=60,
            total=len(serialized_integrations)
            + len(serialized_agents)
            + len(serialized_tools)
            + len(serialized_triggers),
        )

        application = super().import_serialized(
            workspace,
            serialized_values,
            import_export_config,
            id_mapping,
            files_zip,
            storage,
            application_progress,
        )
        application = cast(AgentApplication, application.specific)

        if description:
            application.description = description
            application.save(update_fields=["description"])

        for serialized_integration in serialized_integrations:
            IntegrationHandler().import_integration(
                application,
                serialized_integration,
                id_mapping,
                cache=self.cache,
                files_zip=files_zip,
                storage=storage,
                import_export_config=import_export_config,
            )
            children_progress.increment()

        # Workspace level references (skills, identities) only hold within
        # the workspace they came from; a template install is a duplicate of
        # the template's workspace, not of this one.
        same_workspace = (
            import_export_config.is_duplicate and not import_export_config.is_template
        )

        agents_by_exported_id = {}
        for serialized_agent in serialized_agents:
            agent = AgentDefinition.objects.create(
                application=application,
                name=serialized_agent["name"],
                description=serialized_agent.get("description", ""),
                instructions=serialized_agent.get("instructions", ""),
                memory=serialized_agent.get("memory", ""),
                **self._importable_model(
                    workspace, serialized_agent, import_export_config
                ),
                ai_temperature=serialized_agent.get("ai_temperature"),
            )
            serialized_skills = (
                serialized_agent.get("skills", []) if same_workspace else []
            )
            # Only skills that still exist in this workspace are relinked.
            skill_ids = set(
                WorkspaceSkill.objects.filter(
                    workspace=workspace,
                    id__in=[s["skill_id"] for s in serialized_skills],
                ).values_list("id", flat=True)
            )
            AgentSkill.objects.bulk_create(
                [
                    AgentSkill(
                        agent=agent,
                        skill_id=entry["skill_id"],
                        mode=entry.get("mode") or AgentSkill.Mode.ALWAYS,
                        order=index,
                    )
                    for index, entry in enumerate(serialized_skills)
                    if entry["skill_id"] in skill_ids
                ]
            )
            self._import_example_chats(agent, serialized_agent.get("example_chats", []))
            agents_by_exported_id[serialized_agent["id"]] = agent
            children_progress.increment()

        def import_child_service(serialized_service):
            integration = None
            integration_id = serialized_service.get("integration_id", None)
            if integration_id:
                integration_id = id_mapping.get("integrations", {}).get(
                    integration_id, integration_id
                )
                # The source integration may have been trashed since, or the
                # unmapped id may point at another application's integration;
                # the service then imports without one, like automation does.
                integration = Integration.objects_and_trash.filter(
                    id=integration_id, application_id=application.id
                ).first()

            return ServiceHandler().import_service(
                integration,
                serialized_service,
                id_mapping,
                files_zip=files_zip,
                storage=storage,
                cache=self.cache,
                import_formula=lambda formula, formula_id_mapping, **kwargs: formula,
                # A duplicate must get its own webhook uid, otherwise the
                # copy would receive the original's inbound HTTP calls.
                import_export_config=import_export_config,
            )

        for serialized_trigger in serialized_triggers:
            AgentTrigger.objects.create(
                application=application,
                service=import_child_service(serialized_trigger["service"]),
                # The per-trigger state is preserved; an imported copy still
                # never runs invisibly because `active` is not exported and
                # defaults to off, so the user activates it deliberately.
                enabled=serialized_trigger.get("enabled", True),
            )
            children_progress.increment()

        main_agent = application.agents.first()
        if main_agent is None:
            main_agent = AgentApplicationHandler().create_main_agent(
                application, name=application.name, description=description
            )
        workspace_identity_ids = set(
            Agent.objects.filter(workspace=workspace).values_list("id", flat=True)
        )
        for serialized_tool in serialized_tools:
            service = None
            if serialized_tool.get("service") is not None:
                service = import_child_service(serialized_tool["service"])
            identity_id = serialized_tool.get("identity_id")
            if not same_workspace or identity_id not in workspace_identity_ids:
                identity_id = None
            AgentTool.objects.create(
                agent=main_agent,
                type=serialized_tool["type"],
                name=serialized_tool.get("name", ""),
                config=serialized_tool.get("config", {}),
                order=serialized_tool.get("order", 1),
                service=service,
                identity_id=identity_id,
            )
            children_progress.increment()

        if same_workspace:
            for serialized_channel in serialized_channels:
                channel_type = agent_chat_channel_type_registry.get(
                    serialized_channel["type"]
                )
                AgentChatChannel.objects.create(
                    application=application,
                    type=serialized_channel["type"],
                    name=serialized_channel.get("name", ""),
                    # A fresh uid is generated by the model; public links and
                    # other per-channel identifiers are renewed by the type.
                    config=channel_type.prepare_imported_config(
                        serialized_channel.get("config", {})
                    ),
                    enabled=serialized_channel.get("enabled", True),
                )

        if agent_identity_id is not None and same_workspace:
            identity = Agent.objects.filter(
                id=agent_identity_id, workspace=workspace
            ).first()
            if identity is not None:
                application.agent_identity = identity
                application.save(update_fields=["agent_identity"])
                # The integration import resets the authorized agent, so it
                # must be synced again after all integrations are imported.
                AgentApplicationHandler().sync_agent_identity(application)

        return application

    def enhance_queryset(self, queryset):
        """
        Annotates the header counters in one query. Correlated subqueries keep
        the list query free of joins and GROUP BY, so the cost stays bound to
        the (index-backed) newest trigger run and the pending approvals of
        each agent instead of its whole conversation history.
        """

        from django.db.models import Count, IntegerField, OuterRef, Subquery
        from django.db.models.functions import Coalesce

        pending = (
            AgentChatToolApproval.objects.filter(
                chat__agent__application_id=OuterRef("pk"),
                status=AgentChatToolApproval.Status.PENDING,
            )
            .order_by()
            .values("chat__agent__application_id")
            .annotate(count=Count("id"))
            .values("count")[:1]
        )
        last_run = (
            AgentChat.objects.filter(
                agent__application_id=OuterRef("pk"),
                source=AgentChat.Source.TRIGGER,
                completed_on__isnull=False,
            )
            .order_by("-completed_on")
            .values("completed_on")[:1]
        )
        return queryset.annotate(
            pending_approvals_count=Coalesce(
                Subquery(pending, output_field=IntegerField()), 0
            ),
            last_run_on=Subquery(last_run),
        )

    def enhance_and_filter_queryset_for_workspaces(self, queryset, user, workspaces):
        # The workspace application listing goes through this hook, not
        # `enhance_queryset`; without it every agent application costs two
        # aggregate queries at serialization time.
        return self.enhance_queryset(queryset)
