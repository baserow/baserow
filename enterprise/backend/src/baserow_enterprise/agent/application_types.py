from django.db import transaction

from baserow.core.feature_flags import FF_AGENT_BUILDER, feature_flag_is_enabled
from baserow.core.registries import ApplicationType
from baserow_enterprise.agent.models import AgentApplication


class AgentApplicationType(ApplicationType):
    type = "agent"
    model_class = AgentApplication
    allowed_fields = []
    serializer_field_names = ["name"]

    def export_safe_transaction_context(self, application):
        return transaction.atomic()

    def create_application(self, user, workspace, init_with_data=False, **kwargs):
        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        return super().create_application(
            user, workspace, init_with_data=init_with_data, **kwargs
        )
