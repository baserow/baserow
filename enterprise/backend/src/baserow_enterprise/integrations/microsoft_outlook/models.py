from django.db import models

from baserow.core.formula.field import FormulaField
from baserow.core.services.models import Service


class MicrosoftOutlookBodyType(models.TextChoices):
    PLAIN = "plain", "Plain text"
    HTML = "html", "HTML"


class MicrosoftOutlookSendEmailService(Service):
    """
    Sends an email from the mailbox of a Microsoft integration's account, through
    Outlook.
    """

    to_emails = FormulaField(
        blank=True,
        help_text="The recipients' email addresses, comma separated or a list.",
    )
    cc_emails = FormulaField(
        blank=True,
        help_text="The CC recipients' email addresses, comma separated or a list.",
    )
    bcc_emails = FormulaField(
        blank=True,
        help_text="The BCC recipients' email addresses, comma separated or a list.",
    )
    subject = FormulaField(
        blank=True,
        help_text="The email subject.",
    )
    body_type = models.CharField(
        max_length=10,
        choices=MicrosoftOutlookBodyType.choices,
        default=MicrosoftOutlookBodyType.PLAIN,
        db_default=MicrosoftOutlookBodyType.PLAIN,
        help_text="Whether the body is plain text or HTML.",
    )
    body = FormulaField(
        blank=True,
        help_text="The email body.",
    )
