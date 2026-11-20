from django.conf import settings
from django.db import models


class AgentParticipationRule(models.Model):
    class Capability(models.TextChoices):
        CHAT = "chat", "Chat"
        APPROVE = "approve", "Approve tool calls"
        CONTINUE = "continue", "Continue triggered conversations"

    agent = models.ForeignKey("agent.AgentApplication", on_delete=models.CASCADE)
    capability = models.CharField(max_length=12, choices=Capability.choices)
    role = models.CharField(max_length=12)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="+")
    teams = models.ManyToManyField("baserow_enterprise.Team", related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["agent", "capability"], name="agent_capability_unique"
            )
        ]


DEFAULT_ROLE = {
    AgentParticipationRule.Capability.CHAT: "EDITOR",
    AgentParticipationRule.Capability.APPROVE: "EDITOR",
    AgentParticipationRule.Capability.CONTINUE: "NOBODY",
}


def is_allowed_rule(capability: str, role: str) -> bool:
    """
    Whether a rule may exist: someone must always be able to approve tool calls,
    or no held run could resume.

    :param capability: The capability the rule controls.
    :param role: The lowest role allowed, `CUSTOM` or `NOBODY`.
    :return: False for an approve rule that allows nobody, True otherwise.
    """

    return not (
        capability == AgentParticipationRule.Capability.APPROVE and role == "NOBODY"
    )
