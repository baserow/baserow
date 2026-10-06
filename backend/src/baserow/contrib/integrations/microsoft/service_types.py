from datetime import date, timedelta
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
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)

from .integration_types import MicrosoftIntegrationType
from .models import (
    MicrosoftTeamsSendMessageService,
    OutlookCalendarCreateEventService,
    OutlookCalendarDeleteEventService,
    OutlookCalendarListEventsService,
    OutlookCalendarUpdateEventService,
    OutlookSendEmailService,
)

GRAPH_API_URL = "https://graph.microsoft.com/v1.0"
MAX_LIST_RESULTS = 250


class MicrosoftServiceType(ExternalAPIServiceType):
    integration_type = MicrosoftIntegrationType.type
    provider_name = "Microsoft"
    reconnectable = True
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


def _recipients(value: str):
    return [{"emailAddress": {"address": email}} for email in split_addresses(value)]


class MicrosoftTeamsSendMessageServiceType(MicrosoftServiceType):
    type = "microsoft_teams_send_message"
    model_class = MicrosoftTeamsSendMessageService
    formula_fields = ["team_id", "channel_id", "message"]
    schema_properties = {
        "id": string_property("Message id"),
        "web_url": string_property("Link"),
    }

    def dispatch_data(self, service, resolved_values, dispatch_context):
        team_id = _require(resolved_values, "team_id", "team id")
        channel_id = _require(resolved_values, "channel_id", "channel id")
        message = _require(resolved_values, "message", "message")
        _, body = self.request_json(
            dispatch_context,
            "POST",
            f"{GRAPH_API_URL}/teams/{quote(team_id, safe='')}/channels/"
            f"{quote(channel_id, safe='')}/messages",
            headers=self.auth_headers(service),
            json={"body": {"contentType": "text", "content": message}},
        )
        body = body if isinstance(body, dict) else {}
        return {"id": body.get("id"), "web_url": body.get("webUrl", "")}


class OutlookSendEmailServiceType(MicrosoftServiceType):
    type = "outlook_send_email"
    model_class = OutlookSendEmailService
    formula_fields = ["to_emails", "cc_emails", "bcc_emails", "subject", "body"]
    schema_properties = {"sent": boolean_property("Sent")}

    def dispatch_data(self, service, resolved_values, dispatch_context):
        to_recipients = _recipients(resolved_values.get("to_emails"))
        if not to_recipients:
            raise ServiceImproperlyConfiguredDispatchException(
                "At least one recipient is required."
            )
        message = {
            "subject": resolved_values.get("subject") or "",
            "body": {
                "contentType": "Text",
                "content": resolved_values.get("body") or "",
            },
            "toRecipients": to_recipients,
        }
        cc_recipients = _recipients(resolved_values.get("cc_emails"))
        if cc_recipients:
            message["ccRecipients"] = cc_recipients
        bcc_recipients = _recipients(resolved_values.get("bcc_emails"))
        if bcc_recipients:
            message["bccRecipients"] = bcc_recipients
        # Graph answers 202 with no body.
        self.request_json(
            dispatch_context,
            "POST",
            f"{GRAPH_API_URL}/me/sendMail",
            headers=self.auth_headers(service),
            json={"message": message, "saveToSentItems": True},
        )
        return {"sent": True}


def _event_time(value: str, time_zone: str) -> Optional[Dict[str, str]]:
    value = (value or "").strip()
    if not value:
        return None
    if is_date_only(value):
        value = f"{value}T00:00:00"
    return {"dateTime": value, "timeZone": time_zone or "UTC"}


def _event_body(resolved_values: Dict[str, Any]) -> Dict[str, Any]:
    body: Dict[str, Any] = {}
    subject = (resolved_values.get("subject") or "").strip()
    if subject:
        body["subject"] = subject
    description = resolved_values.get("body") or ""
    if description.strip():
        body["body"] = {"contentType": "Text", "content": description}
    location = (resolved_values.get("location") or "").strip()
    if location:
        body["location"] = {"displayName": location}
    time_zone = (resolved_values.get("time_zone") or "").strip()
    start = (resolved_values.get("start") or "").strip()
    end = (resolved_values.get("end") or "").strip()
    if start and is_date_only(start):
        # Graph wants an all-day event to run from midnight to the next
        # midnight; a single date means that one day.
        body["isAllDay"] = True
        if not end or end == start:
            end = (date.fromisoformat(start) + timedelta(days=1)).isoformat()
    for name, value in (("start", start), ("end", end)):
        moment = _event_time(value, time_zone)
        if moment:
            body[name] = moment
    attendees = split_addresses(resolved_values.get("attendees"))
    if attendees:
        body["attendees"] = [
            {"emailAddress": {"address": email}, "type": "required"}
            for email in attendees
        ]
    return body


def _event_output(event: dict) -> Dict[str, Any]:
    start = event.get("start") or {}
    end = event.get("end") or {}
    body = event.get("body") or {}
    return {
        "id": event.get("id"),
        "subject": event.get("subject", ""),
        "body": event.get("bodyPreview") or body.get("content", ""),
        "location": (event.get("location") or {}).get("displayName", ""),
        "start": start.get("dateTime", ""),
        "end": end.get("dateTime", ""),
        "time_zone": start.get("timeZone", ""),
        "is_all_day": bool(event.get("isAllDay")),
        "web_link": event.get("webLink", ""),
        "attendees": ", ".join(
            (attendee.get("emailAddress") or {}).get("address", "")
            for attendee in event.get("attendees") or []
            if (attendee.get("emailAddress") or {}).get("address")
        ),
    }


EVENT_PROPERTIES = {
    "id": string_property("Event id"),
    "subject": string_property("Title"),
    "body": string_property("Description"),
    "location": string_property("Location"),
    "start": string_property("Start"),
    "end": string_property("End"),
    "time_zone": string_property("Time zone"),
    "is_all_day": boolean_property("All day"),
    "web_link": string_property("Link"),
    "attendees": string_property("Attendees"),
}


class OutlookCalendarServiceType(MicrosoftServiceType):
    def events_url(self, resolved_values: Dict[str, Any]) -> str:
        calendar_id = (resolved_values.get("calendar_id") or "").strip()
        if calendar_id:
            return f"{GRAPH_API_URL}/me/calendars/{quote(calendar_id, safe='')}/events"
        return f"{GRAPH_API_URL}/me/events"


class OutlookCalendarCreateEventServiceType(OutlookCalendarServiceType):
    type = "outlook_calendar_create_event"
    model_class = OutlookCalendarCreateEventService
    formula_fields = [
        "calendar_id",
        "subject",
        "body",
        "location",
        "start",
        "end",
        "time_zone",
        "attendees",
    ]
    schema_properties = EVENT_PROPERTIES

    def dispatch_data(self, service, resolved_values, dispatch_context):
        _require(resolved_values, "subject", "event title")
        body = _event_body(resolved_values)
        if "start" not in body or "end" not in body:
            raise ServiceImproperlyConfiguredDispatchException(
                "The start and end of the event are required."
            )
        _, event = self.request_json(
            dispatch_context,
            "POST",
            self.events_url(resolved_values),
            headers=self.auth_headers(service),
            json=body,
        )
        return _event_output(event if isinstance(event, dict) else {})


class OutlookCalendarUpdateEventServiceType(OutlookCalendarServiceType):
    type = "outlook_calendar_update_event"
    model_class = OutlookCalendarUpdateEventService
    formula_fields = [
        "calendar_id",
        "event_id",
        "subject",
        "body",
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
            f"{self.events_url(resolved_values)}/{quote(event_id, safe='')}",
            headers=self.auth_headers(service),
            json=body,
        )
        return _event_output(event if isinstance(event, dict) else {})


class OutlookCalendarDeleteEventServiceType(OutlookCalendarServiceType):
    type = "outlook_calendar_delete_event"
    model_class = OutlookCalendarDeleteEventService
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
            f"{self.events_url(resolved_values)}/{quote(event_id, safe='')}",
            headers=self.auth_headers(service),
        )
        return {"event_id": event_id, "deleted": True}


class OutlookCalendarListEventsServiceType(OutlookCalendarServiceType):
    type = "outlook_calendar_list_events"
    model_class = OutlookCalendarListEventsService
    formula_fields = ["calendar_id", "start", "end"]
    plain_fields = ["max_results"]
    schema_properties = {
        "events": array_property("Events", EVENT_PROPERTIES),
        "count": number_property("Count"),
    }

    def dispatch_data(self, service, resolved_values, dispatch_context):
        top = max(1, min(service.max_results or 50, MAX_LIST_RESULTS))
        params: Dict[str, Any] = {"$top": top, "$orderby": "start/dateTime"}
        start = (resolved_values.get("start") or "").strip()
        end = (resolved_values.get("end") or "").strip()
        url = self.events_url(resolved_values)
        if start and end:
            # The calendar view expands recurring events within a window; the
            # plain list does not, so a window is the better answer.
            url = url[: -len("/events")] + "/calendarView"
            params["startDateTime"] = start
            params["endDateTime"] = end
        elif start or end:
            raise ServiceImproperlyConfiguredDispatchException(
                "Fill in both the start and the end to list a time window, or "
                "neither to list upcoming events."
            )
        _, body = self.request_json(
            dispatch_context,
            "GET",
            url,
            headers=self.auth_headers(service),
            params=params,
        )
        items = body.get("value") if isinstance(body, dict) else None
        events = [_event_output(item) for item in items or [] if isinstance(item, dict)]
        return {"events": events, "count": len(events)}
