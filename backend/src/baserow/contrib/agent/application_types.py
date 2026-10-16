from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.db.transaction import Atomic

from baserow.contrib.agent.models import AgentApplication
from baserow.core.feature_flags import FF_AGENT_BUILDER, feature_flag_is_enabled
from baserow.core.models import Application, Workspace
from baserow.core.registries import ApplicationType


class AgentApplicationType(ApplicationType):
    type = "agent"
    model_class = AgentApplication
    allowed_fields = []
    serializer_field_names = ["name"]

    def export_safe_transaction_context(self, application: AgentApplication) -> Atomic:
        return transaction.atomic()

    def create_application(
        self,
        user: AbstractUser,
        workspace: Workspace,
        init_with_data: bool = False,
        **kwargs,
    ) -> Application:
        feature_flag_is_enabled(FF_AGENT_BUILDER, raise_if_disabled=True)
        return super().create_application(
            user, workspace, init_with_data=init_with_data, **kwargs
        )
