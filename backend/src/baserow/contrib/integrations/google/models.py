from django.db import models

from baserow.contrib.integrations.oauth2.models import OAuth2Integration
from baserow.core.formula.field import FormulaField
from baserow.core.services.models import Service


class GoogleIntegration(OAuth2Integration):
    """A Google account connected through Google's consent screen."""


class GmailSendEmailService(Service):
    to_emails = FormulaField(
        default="",
        help_text="Recipient addresses, separated by commas.",
    )
    cc_emails = FormulaField(default="", help_text="CC addresses, separated by commas.")
    bcc_emails = FormulaField(
        default="", help_text="BCC addresses, separated by commas."
    )
    subject = FormulaField(default="", help_text="The subject line.")
    body = FormulaField(default="", help_text="The plain text body.")


class GoogleCalendarEventServiceMixin(models.Model):
    calendar_id = FormulaField(
        default="'primary'",
        help_text="The calendar id; 'primary' is the account's main calendar.",
    )

    class Meta:
        abstract = True


class GoogleCalendarEventFieldsMixin(models.Model):
    summary = FormulaField(default="", help_text="The event title.")
    description = FormulaField(default="", help_text="The event description.")
    location = FormulaField(default="", help_text="Where the event takes place.")
    start = FormulaField(
        default="",
        help_text="Start as an ISO 8601 date-time (2026-10-06T09:00:00+02:00) or a "
        "date (2026-10-06) for an all-day event.",
    )
    end = FormulaField(default="", help_text="End, in the same format as the start.")
    time_zone = FormulaField(
        default="",
        help_text="IANA time zone (Europe/Amsterdam) applied when the start and end "
        "carry no offset.",
    )
    attendees = FormulaField(
        default="", help_text="Attendee email addresses, separated by commas."
    )

    class Meta:
        abstract = True


class GoogleCalendarCreateEventService(
    Service, GoogleCalendarEventServiceMixin, GoogleCalendarEventFieldsMixin
):
    pass


class GoogleCalendarUpdateEventService(
    Service, GoogleCalendarEventServiceMixin, GoogleCalendarEventFieldsMixin
):
    event_id = FormulaField(default="", help_text="The id of the event to change.")


class GoogleCalendarDeleteEventService(Service, GoogleCalendarEventServiceMixin):
    event_id = FormulaField(default="", help_text="The id of the event to delete.")


class GoogleCalendarListEventsService(Service, GoogleCalendarEventServiceMixin):
    time_min = FormulaField(
        default="",
        help_text="Only events ending after this ISO 8601 date-time.",
    )
    time_max = FormulaField(
        default="",
        help_text="Only events starting before this ISO 8601 date-time.",
    )
    query = FormulaField(
        default="", help_text="Free text matched against the events' fields."
    )
    max_results = models.PositiveIntegerField(
        default=50, help_text="The most events to return (1-250)."
    )
