from baserow.core.handler import CoreHandler
from baserow.core.operations import ListApplicationsWorkspaceOperationType
from baserow_premium.row_comments.mention_types import (
    RowCommentMentionTargetType,
    _int_ids,
)

from .models import AgentApplication


class AgentApplicationMentionTargetType(RowCommentMentionTargetType):
    """
    An agent application addressed in a row comment. Being mentioned does
    nothing by itself here: the comment event carries the mentioned agents
    and the agent's row comment trigger decides whether it runs
    (`RowCommentCreatedAgentTriggerType.should_run`).
    """

    type = "application"

    def resolve(self, ids, workspace):
        return list(
            AgentApplication.objects.filter(
                id__in=_int_ids(ids), workspace=workspace, trashed=False
            )
        )

    def attach(self, row_comment, targets):
        row_comment.mentioned_applications.set(targets)

    def get_attached(self, row_comment):
        return list(row_comment.mentioned_applications.all())

    def get_signal_kwargs(self, targets):
        return {"mentioned_applications": list(targets)}

    def get_event_payload(self, targets):
        return {"mentioned_application_ids": [target.id for target in targets]}

    def get_event_schema(self):
        return {
            "mentioned_application_ids": {"type": "array", "title": "Mentioned agents"}
        }

    def list_mentionable(self, user, table):
        """
        The agents that asked to run on mentions only for this table. An
        agent without that option reacts to every comment, so a mention would
        mean nothing and it is left out.
        """

        from .triggers.trigger_types import RowCommentCreatedAgentTriggerType

        option = RowCommentCreatedAgentTriggerType.ONLY_WHEN_MENTIONED
        workspace = table.database.workspace
        applications = CoreHandler().filter_queryset(
            user,
            ListApplicationsWorkspaceOperationType.type,
            AgentApplication.objects.filter(workspace=workspace, active=True),
            workspace=workspace,
        )
        targets = []
        for application in applications.prefetch_related("triggers__service"):
            for trigger in application.triggers.all():
                if not trigger.enabled or not (trigger.config or {}).get(option):
                    continue
                service = trigger.service.specific
                if (
                    service.get_type().type
                    == RowCommentCreatedAgentTriggerType.service_type
                    and getattr(service, "table_id", None) == table.id
                ):
                    targets.append(
                        {
                            "type": self.type,
                            "id": application.id,
                            "name": application.name,
                        }
                    )
                    break
        return targets
