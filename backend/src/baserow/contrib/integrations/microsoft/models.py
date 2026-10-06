from django.db import models

from baserow.contrib.integrations.oauth2.models import OAuth2Integration
from baserow.core.formula.field import FormulaField
from baserow.core.services.models import Service


class MicrosoftIntegration(OAuth2Integration):
    """A Microsoft 365 account connected through the Microsoft identity platform."""

    tenant = models.CharField(
        max_length=255,
        default="common",
        help_text="The Entra tenant the app registration lives in: 'common' for "
        "any account, 'organizations' for work accounts, or a tenant id.",
    )


class MicrosoftTeamsSendMessageService(Service):
    team_id = FormulaField(default="", help_text="The id of the team.")
    channel_id = FormulaField(default="", help_text="The id of the channel.")
    message = FormulaField(default="", help_text="The message to post.")


class OutlookSendEmailService(Service):
    to_emails = FormulaField(
        default="", help_text="Recipient addresses, separated by commas."
    )
    cc_emails = FormulaField(default="", help_text="CC addresses, separated by commas.")
    bcc_emails = FormulaField(
        default="", help_text="BCC addresses, separated by commas."
    )
    subject = FormulaField(default="", help_text="The subject line.")
    body = FormulaField(default="", help_text="The plain text body.")


class OutlookCalendarServiceMixin(models.Model):
    calendar_id = FormulaField(
        default="",
        help_text="The calendar id; leave empty for the account's default calendar.",
    )

    class Meta:
        abstract = True


class OutlookCalendarEventFieldsMixin(models.Model):
    subject = FormulaField(default="", help_text="The event title.")
    body = FormulaField(default="", help_text="The event description.")
    location = FormulaField(default="", help_text="Where the event takes place.")
    start = FormulaField(
        default="",
        help_text="Start as an ISO 8601 date-time (2026-10-06T09:00:00) or a date "
        "(2026-10-06) for an all-day event.",
    )
    end = FormulaField(default="", help_text="End, in the same format as the start.")
    time_zone = FormulaField(
        default="'UTC'",
        help_text="The IANA time zone (Europe/Amsterdam) of the start and end.",
    )
    attendees = FormulaField(
        default="", help_text="Attendee email addresses, separated by commas."
    )

    class Meta:
        abstract = True


class OutlookCalendarCreateEventService(
    Service, OutlookCalendarServiceMixin, OutlookCalendarEventFieldsMixin
):
    pass


class OutlookCalendarUpdateEventService(
    Service, OutlookCalendarServiceMixin, OutlookCalendarEventFieldsMixin
):
    event_id = FormulaField(default="", help_text="The id of the event to change.")


class OutlookCalendarDeleteEventService(Service, OutlookCalendarServiceMixin):
    event_id = FormulaField(default="", help_text="The id of the event to delete.")


class OutlookCalendarListEventsService(Service, OutlookCalendarServiceMixin):
    start = FormulaField(
        default="", help_text="Only events ending after this ISO 8601 date-time."
    )
    end = FormulaField(
        default="", help_text="Only events starting before this ISO 8601 date-time."
    )
    max_results = models.PositiveIntegerField(
        default=50, help_text="The most events to return (1-250)."
    )
