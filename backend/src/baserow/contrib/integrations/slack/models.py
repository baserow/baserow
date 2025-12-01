from django.db import models

from baserow.core.formula.field import FormulaField
from baserow.core.integrations.models import Integration
from baserow.core.services.models import Service


class SlackBotIntegration(Integration):
    token = models.CharField(
        max_length=255,
        help_text="The Bot User OAuth Token listed in "
        "your Slack bot's OAuth & Permissions page.",
    )


class SlackWriteMessageService(Service):
    channel = models.CharField(
        max_length=80,
        help_text="The Slack channel ID where the message will be sent.",
    )
    text = FormulaField(
        help_text="The text content of the Slack message.",
    )
