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
from baserow.core.storage import ExportZipFile
from baserow.core.utils import ChildProgressBuilder

from .handler import AgentApplicationHandler
from .models import (
    AgentApplication,
    AgentChat,
    AgentChatChannel,
    AgentChatToolApproval,
    AgentDefinition,
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
    "permissions",
    "web_search",
    "create_identity",
]
RUN_MODES = ["chat", "daily", "weekly"]
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
            help_text="Adds a periodic trigger when not `chat` (create only).",
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
    }
    supports_integrations = True

    def get_api_urls(self):
        from baserow_enterprise.api.agent_application import urls as api_urls

        return [
            path("agent_application/", include(api_urls, namespace=self.type)),
        ]

    def export_safe_transaction_context(self, application: Application) -> Atomic:
        return transaction.atomic()

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
            )
            for i in IntegrationHandler().get_integrations(agent_application)
        ]

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
                "config": tool.config,
                "order": tool.order,
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
            )
            children_progress.increment()

        agents_by_exported_id = {}
        for serialized_agent in serialized_agents:
            agent = AgentDefinition.objects.create(
                application=application,
                name=serialized_agent["name"],
                description=serialized_agent.get("description", ""),
                instructions=serialized_agent.get("instructions", ""),
                memory=serialized_agent.get("memory", ""),
                ai_generative_ai_type=serialized_agent.get("ai_generative_ai_type"),
                ai_generative_ai_model=serialized_agent.get("ai_generative_ai_model"),
                ai_temperature=serialized_agent.get("ai_temperature"),
            )
            agents_by_exported_id[serialized_agent["id"]] = agent
            children_progress.increment()

        def import_child_service(serialized_service):
            integration = None
            integration_id = serialized_service.get("integration_id", None)
            if integration_id:
                integration_id = id_mapping.get("integrations", {}).get(
                    integration_id, integration_id
                )
                integration = Integration.objects.get(id=integration_id)

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
        for serialized_tool in serialized_tools:
            service = None
            if serialized_tool.get("service") is not None:
                service = import_child_service(serialized_tool["service"])
            AgentTool.objects.create(
                agent=main_agent,
                type=serialized_tool["type"],
                name=serialized_tool.get("name", ""),
                config=serialized_tool.get("config", {}),
                order=serialized_tool.get("order", 1),
                service=service,
            )
            children_progress.increment()

        for serialized_channel in serialized_channels:
            # A fresh uid is generated so the copy gets its own webhook URL.
            AgentChatChannel.objects.create(
                application=application,
                type=serialized_channel["type"],
                name=serialized_channel.get("name", ""),
                config=serialized_channel.get("config", {}),
                enabled=serialized_channel.get("enabled", True),
            )

        if agent_identity_id is not None and import_export_config.is_duplicate:
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

    def enhance_and_filter_queryset(self, queryset, user, workspace):
        # The workspace application listing goes through this hook, not
        # `enhance_queryset`; without it every agent application costs two
        # aggregate queries at serialization time.
        return self.enhance_queryset(queryset)
