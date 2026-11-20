from typing import Any

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
        return (
            f"{event_payload['user_name']} commented on row {event_payload['row_id']} "
            f"in table {event_payload['table_id']}: {event_payload['text']}"
        )
