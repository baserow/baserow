from django.conf import settings
from django.db import models


class AgentParticipationRule(models.Model):
    class Capability(models.TextChoices):
        CHAT = "chat", "Chat"
        APPROVE = "approve", "Approve and continue"

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
