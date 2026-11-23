from typing import Any

from baserow.contrib.agent.triggers.data_providers import trigger_data_as_text
from baserow.contrib.agent.triggers.registries import AgentTriggerType
from baserow_enterprise.integrations.local_baserow.models import (
    LocalBaserowRowCommentPosted,
)
from baserow_enterprise.integrations.local_baserow.service_types import (
    LocalBaserowRowCommentPostedTriggerServiceType,
)


class RowCommentPostedAgentTriggerType(AgentTriggerType):
    type = LocalBaserowRowCommentPostedTriggerServiceType.type
    unused_service_fields = ("integration_id",)

    def get_event_text(
        self, service: LocalBaserowRowCommentPosted, event_payload: dict[str, Any]
    ) -> str:
        return trigger_data_as_text(event_payload)
