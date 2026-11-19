from django.dispatch import receiver

from rest_framework.exceptions import ValidationError

from baserow.contrib.agent.models import AgentTrigger
from baserow.contrib.agent.signals import before_agent_trigger_deleted
from baserow_enterprise.features import RBAC
from baserow_premium.license.handler import LicenseHandler

from .models import AgentParticipationRule


@receiver(before_agent_trigger_deleted)
def keep_trigger_for_trigger_only_agent(sender, trigger, **kwargs):
    agent = trigger.agent
    if (
        AgentParticipationRule.objects.filter(
            agent=agent, capability="chat", role="NOBODY"
        ).exists()
        and LicenseHandler.workspace_has_feature(RBAC, agent.workspace)
        and not AgentTrigger.objects.filter(agent=agent).exclude(pk=trigger.pk).exists()
    ):
        raise ValidationError(
            {"trigger": "Enable chat before deleting the last trigger."}
        )
