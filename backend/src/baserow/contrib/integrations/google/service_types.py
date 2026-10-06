import base64
from email.message import EmailMessage
from typing import Any, Dict, Optional
from urllib.parse import quote

from baserow.contrib.integrations.external_api import (
    ExternalAPIServiceType,
    array_property,
    boolean_property,
    is_date_only,
    number_property,
    split_addresses,
    string_property,
)
from baserow.contrib.integrations.oauth2.handler import OAuth2IntegrationHandler
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)

from .integration_types import GoogleIntegrationType
from .models import (
    GmailSendEmailService,
    GoogleCalendarCreateEventService,
    GoogleCalendarDeleteEventService,
    GoogleCalendarListEventsService,
    GoogleCalendarUpdateEventService,
)

GMAIL_API_URL = "https://gmail.googleapis.com/gmail/v1"
CALENDAR_API_URL = "https://www.googleapis.com/calendar/v3"
MAX_LIST_RESULTS = 250


class GoogleServiceType(ExternalAPIServiceType):
    integration_type = GoogleIntegrationType.type
    provider_name = "Google"
    reconnectable = True
    # The access token refresh may add a request.
    request_count = 2

    def auth_headers(self, service) -> Dict[str, str]:
        integration = self.get_integration(service)
        token = OAuth2IntegrationHandler().get_access_token(integration)
        return {"Authorization": f"Bearer {token}"}


def _require(resolved_values: Dict[str, Any], name: str, label: str) -> str:
    value = (resolved_values.get(name) or "").strip()
    if not value:
        raise ServiceImproperlyConfiguredDispatchException(f"The {label} is missing.")
    return value


def _event_time(value: str, time_zone: str) -> Optional[Dict[str, str]]:
    value = (value or "").strip()
    if not value:
        return None
    if is_date_only(value):
        return {"date": value}
    moment = {"dateTime": value}
    if time_zone:
        moment["timeZone"] = time_zone
    return moment


def _event_body(resolved_values: Dict[str, Any]) -> Dict[str, Any]:
    """Only what the user filled in, so an update leaves the rest untouched."""

    body: Dict[str, Any] = {}
    for name in ("summary", "description", "location"):
        if (resolved_values.get(name) or "").strip():
            body[name] = resolved_values[name].strip()
    time_zone = (resolved_values.get("time_zone") or "").strip()
    for name in ("start", "end"):
        moment = _event_time(resolved_values.get(name), time_zone)
        if moment:
            body[name] = moment
    attendees = split_addresses(resolved_values.get("attendees"))
    if attendees:
        body["attendees"] = [{"email": email} for email in attendees]
    return body


def _event_output(event: dict) -> Dict[str, Any]:
    start = event.get("start") or {}
    end = event.get("end") or {}
    return {
        "id": event.get("id"),
        "summary": event.get("summary", ""),
        "description": event.get("description", ""),
        "location": event.get("location", ""),
        "start": start.get("dateTime") or start.get("date") or "",
        "end": end.get("dateTime") or end.get("date") or "",
        "status": event.get("status", ""),
        "html_link": event.get("htmlLink", ""),
        "attendees": ", ".join(
            attendee.get("email", "")
            for attendee in event.get("attendees") or []
            if attendee.get("email")
        ),
    }


EVENT_PROPERTIES = {
    "id": string_property("Event id"),
    "summary": string_property("Title"),
    "description": string_property("Description"),
    "location": string_property("Location"),
    "start": string_property("Start"),
    "end": string_property("End"),
    "status": string_property("Status"),
    "html_link": string_property("Link"),
    "attendees": string_property("Attendees"),
}


class GmailSendEmailServiceType(GoogleServiceType):
    type = "gmail_send_email"
    model_class = GmailSendEmailService
    formula_fields = ["to_emails", "cc_emails", "bcc_emails", "subject", "body"]
    schema_properties = {
        "id": string_property("Message id"),
        "thread_id": string_property("Thread id"),
    }

    def dispatch_data(
        self,
        service: GmailSendEmailService,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        to_emails = split_addresses(resolved_values.get("to_emails"))
        if not to_emails:
            raise ServiceImproperlyConfiguredDispatchException(
                "At least one recipient is required."
            )
        headers = self.auth_headers(service)
        message = EmailMessage()
        message["To"] = ", ".join(to_emails)
        cc_emails = split_addresses(resolved_values.get("cc_emails"))
        if cc_emails:
            message["Cc"] = ", ".join(cc_emails)
        bcc_emails = split_addresses(resolved_values.get("bcc_emails"))
        if bcc_emails:
            message["Bcc"] = ", ".join(bcc_emails)
        message["Subject"] = resolved_values.get("subject") or ""
        message.set_content(resolved_values.get("body") or "")
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        _, body = self.request_json(
            dispatch_context,
            "POST",
            f"{GMAIL_API_URL}/users/me/messages/send",
            headers=headers,
            json={"raw": raw},
        )
        body = body if isinstance(body, dict) else {}
        return {"id": body.get("id"), "thread_id": body.get("threadId")}


class GoogleCalendarServiceType(GoogleServiceType):
    def calendar_url(self, resolved_values: Dict[str, Any]) -> str:
        calendar_id = (resolved_values.get("calendar_id") or "").strip() or "primary"
        return f"{CALENDAR_API_URL}/calendars/{quote(calendar_id, safe='')}/events"


class GoogleCalendarCreateEventServiceType(GoogleCalendarServiceType):
    type = "google_calendar_create_event"
    model_class = GoogleCalendarCreateEventService
    formula_fields = [
        "calendar_id",
        "summary",
        "description",
        "location",
        "start",
        "end",
        "time_zone",
        "attendees",
    ]
    schema_properties = EVENT_PROPERTIES

    def dispatch_data(self, service, resolved_values, dispatch_context):
        _require(resolved_values, "summary", "event title")
        body = _event_body(resolved_values)
        if "start" not in body or "end" not in body:
            raise ServiceImproperlyConfiguredDispatchException(
                "The start and end of the event are required."
            )
        _, event = self.request_json(
            dispatch_context,
            "POST",
            self.calendar_url(resolved_values),
            headers=self.auth_headers(service),
            json=body,
        )
        return _event_output(event if isinstance(event, dict) else {})


class GoogleCalendarUpdateEventServiceType(GoogleCalendarServiceType):
    type = "google_calendar_update_event"
    model_class = GoogleCalendarUpdateEventService
    formula_fields = [
        "calendar_id",
        "event_id",
        "summary",
        "description",
        "location",
        "start",
        "end",
        "time_zone",
        "attendees",
    ]
    schema_properties = EVENT_PROPERTIES

    def dispatch_data(self, service, resolved_values, dispatch_context):
        event_id = _require(resolved_values, "event_id", "event id")
        body = _event_body(resolved_values)
        if not body:
            raise ServiceImproperlyConfiguredDispatchException(
                "Nothing to change: fill in at least one event property."
            )
        _, event = self.request_json(
            dispatch_context,
            "PATCH",
            f"{self.calendar_url(resolved_values)}/{quote(event_id, safe='')}",
            headers=self.auth_headers(service),
            json=body,
        )
        return _event_output(event if isinstance(event, dict) else {})


class GoogleCalendarDeleteEventServiceType(GoogleCalendarServiceType):
    type = "google_calendar_delete_event"
    model_class = GoogleCalendarDeleteEventService
    formula_fields = ["calendar_id", "event_id"]
    schema_properties = {
        "event_id": string_property("Event id"),
        "deleted": boolean_property("Deleted"),
    }

    def dispatch_data(self, service, resolved_values, dispatch_context):
        event_id = _require(resolved_values, "event_id", "event id")
        self.request_json(
            dispatch_context,
            "DELETE",
            f"{self.calendar_url(resolved_values)}/{quote(event_id, safe='')}",
            headers=self.auth_headers(service),
        )
        return {"event_id": event_id, "deleted": True}


class GoogleCalendarListEventsServiceType(GoogleCalendarServiceType):
    type = "google_calendar_list_events"
    model_class = GoogleCalendarListEventsService
    formula_fields = ["calendar_id", "time_min", "time_max", "query"]
    plain_fields = ["max_results"]
    schema_properties = {
        "events": array_property("Events", EVENT_PROPERTIES),
        "count": number_property("Count"),
    }

    def dispatch_data(self, service, resolved_values, dispatch_context):
        params = {
            # Expanded occurrences in start order, which is what a person
            # expects of a list; Google only orders expanded events.
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": max(1, min(service.max_results or 50, MAX_LIST_RESULTS)),
        }
        for param, name in (("timeMin", "time_min"), ("timeMax", "time_max")):
            value = (resolved_values.get(name) or "").strip()
            if value:
                params[param] = value
        query = (resolved_values.get("query") or "").strip()
        if query:
            params["q"] = query
        _, body = self.request_json(
            dispatch_context,
            "GET",
            self.calendar_url(resolved_values),
            headers=self.auth_headers(service),
            params=params,
        )
        items = body.get("items") if isinstance(body, dict) else None
        events = [_event_output(item) for item in items or [] if isinstance(item, dict)]
        return {"events": events, "count": len(events)}
