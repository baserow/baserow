from django.db import transaction
from django.urls import include, path

from baserow.core.feature_flags import FF_AGENT_BUILDER
from baserow.core.handler import CoreHandler
from baserow.core.models import TrashEntry
from baserow.core.registries import ApplicationType
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import ChildProgressBuilder
from baserow_enterprise.agent_builder.models import AgentBuilder, AgentDefinition
from baserow_enterprise.agent_builder.operations import ReadAgentOperationType
from baserow_enterprise.agent_builder.trash_types import AgentTrashableItemType


class AgentBuilderApplicationType(ApplicationType):
    type = "agent_builder"
    model_class = AgentBuilder
    feature_flag = FF_AGENT_BUILDER
    allowed_fields = []
    serializer_field_names = ["name"]

    def get_api_urls(self):
        from .api import urls as api_urls

        return [path("agent-builder/", include(api_urls, namespace=self.type))]

    def prepare_value_for_db(self, values, instance=None):
        self.check_feature_flag()
        return super().prepare_value_for_db(values, instance)

    def create_application(self, user, workspace, init_with_data=False, **kwargs):
        self.check_feature_flag()
        return super().create_application(user, workspace, init_with_data, **kwargs)

    def init_application(self, user, application):
        # A new builder is intentionally empty. Creating agents remains a separate,
        # permission-checked action, including when init_with_data is requested.
        self.check_feature_flag()

    def export_safe_transaction_context(self, application):
        return transaction.atomic()

    def pre_delete(self, application):
        # Permanent deletion is operational cleanup and must still work with the
        # flag disabled, including trash entries for individually deleted agents.
        agents = AgentDefinition.objects_and_trash.filter(agent_builder=application)
        TrashEntry.objects.filter(
            trash_item_type=AgentTrashableItemType.type,
            trash_item_id__in=agents.values("id"),
        ).delete()
        for agent in agents:
            TrashHandler.permanently_delete(agent)

    def export_serialized(
        self,
        application,
        import_export_config,
        files_zip=None,
        storage=None,
        progress_builder=None,
    ):
        serialized = super().export_serialized(
            application,
            import_export_config,
            files_zip=files_zip,
            storage=storage,
        )
        # Backups and snapshot copies may have a trashed or workspace-less parent;
        # only the child's own trash state decides whether it belongs in the export.
        agents = AgentDefinition.objects_and_trash.filter(
            agent_builder=application, trashed=False
        )
        if import_export_config.copied_by is not None and application.workspace_id:
            agents = CoreHandler().filter_queryset(
                import_export_config.copied_by,
                ReadAgentOperationType.type,
                agents,
                workspace=application.workspace,
            )
        serialized["agents"] = [
            self.export_serialized_structure_with_registry(
                application.get_root(),
                agent,
                {"id": agent.id, "name": agent.name, "order": agent.order},
                import_export_config,
            )
            for agent in agents
        ]
        progress = ChildProgressBuilder.build(progress_builder, child_total=1)
        progress.increment()
        return serialized

    def import_serialized(
        self,
        workspace,
        serialized_values,
        import_export_config,
        id_mapping,
        files_zip=None,
        storage=None,
        progress_builder=None,
    ):
        self.check_feature_flag()
        application_values = serialized_values.copy()
        serialized_agents = application_values.pop("agents", [])
        application = super().import_serialized(
            workspace,
            application_values,
            import_export_config,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
        )
        mapping = id_mapping.setdefault("agent_builder_agents", {})
        progress = ChildProgressBuilder.build(
            progress_builder, child_total=len(serialized_agents) + 1
        )
        progress.increment()
        for values in serialized_agents:
            agent = AgentDefinition.objects.create(
                agent_builder=application, name=values["name"], order=values["order"]
            )
            mapping[values["id"]] = agent.id
            self.import_serialized_structure_with_registry(
                id_mapping, agent, values, import_export_config, workspace
            )
            progress.increment()
        return application
