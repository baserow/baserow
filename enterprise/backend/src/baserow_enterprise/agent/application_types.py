from django.db import transaction

from baserow.core.feature_flags import FF_AGENT_BUILDER
from baserow.core.registries import ApplicationType
from baserow_enterprise.agent.models import AgentApplication


class AgentApplicationType(ApplicationType):
    type = "agent"
    model_class = AgentApplication
    feature_flag = FF_AGENT_BUILDER
    allowed_fields = []
    serializer_field_names = ["name"]

    def export_safe_transaction_context(self, application):
        return transaction.atomic()

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
        return super().import_serialized(
            workspace,
            serialized_values,
            import_export_config,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            progress_builder=progress_builder,
        )
