from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

import pytest

from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.test_utils.pytest_conftest import FakeDispatchContext
from tests.baserow.contrib.integrations.external_api_test_utils import fake_response

SEND = "baserow.contrib.integrations.external_api.send_http_request"
GRAPH = "https://graph.microsoft.com/v1.0"


def connected():
    return {
        "access_token": "ms-at",
        "access_token_expires_at": timezone.now() + timedelta(hours=1),
    }


@pytest.mark.django_db
def test_teams_send_message(data_fixture):
    service = data_fixture.create_microsoft_teams_send_message_service(
        integration_args=connected(),
        team_id="'team-1'",
        channel_id="'19:abc@thread.tacv2'",
        message="'Build is green'",
    )
    body = {"id": "m1", "webUrl": "https://teams.microsoft.com/l/message/m1"}
    with patch(SEND, return_value=fake_response(201, body)) as send:
        result = service.get_type().dispatch(service, FakeDispatchContext())

    assert send.call_args.args == (
        "POST",
        f"{GRAPH}/teams/team-1/channels/19%3Aabc%40thread.tacv2/messages",
    )
    assert send.call_args.kwargs["headers"] == {"Authorization": "Bearer ms-at"}
    assert send.call_args.kwargs["json"] == {
        "body": {"contentType": "text", "content": "Build is green"}
    }
    assert result.data == {"id": "m1", "web_url": body["webUrl"]}

    missing = data_fixture.create_microsoft_teams_send_message_service(
        integration_args=connected(), team_id="'t'", message="'x'"
    )
    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        missing.get_type().dispatch(missing, FakeDispatchContext())


@pytest.mark.django_db
def test_outlook_send_email(data_fixture):
    service = data_fixture.create_outlook_send_email_service(
        integration_args=connected(),
        to_emails="'a@example.com'",
        bcc_emails="'b@example.com'",
        subject="'Hi'",
        body="'Body'",
    )
    with patch(SEND, return_value=fake_response(202)) as send:
        result = service.get_type().dispatch(service, FakeDispatchContext())

    assert send.call_args.args == ("POST", f"{GRAPH}/me/sendMail")
    assert send.call_args.kwargs["json"] == {
        "message": {
            "subject": "Hi",
            "body": {"contentType": "Text", "content": "Body"},
            "toRecipients": [{"emailAddress": {"address": "a@example.com"}}],
            "bccRecipients": [{"emailAddress": {"address": "b@example.com"}}],
        },
        "saveToSentItems": True,
    }
    assert result.data == {"sent": True}


@pytest.mark.django_db
def test_outlook_calendar_create_event_all_day_spans_to_the_next_day(data_fixture):
    service = data_fixture.create_outlook_calendar_create_event_service(
        integration_args=connected(),
        calendar_id="'cal-1'",
        subject="'Offsite'",
        body="'Agenda'",
        start="'2026-10-07'",
        time_zone="'Europe/Amsterdam'",
        attendees="'a@example.com'",
    )
    event = {
        "id": "e1",
        "subject": "Offsite",
        "isAllDay": True,
        "start": {
            "dateTime": "2026-10-07T00:00:00.0000000",
            "timeZone": "Europe/Amsterdam",
        },
        "end": {
            "dateTime": "2026-10-08T00:00:00.0000000",
            "timeZone": "Europe/Amsterdam",
        },
        "webLink": "https://outlook.office365.com/e1",
    }
    with patch(SEND, return_value=fake_response(201, event)) as send:
        result = service.get_type().dispatch(service, FakeDispatchContext())

    assert send.call_args.args == ("POST", f"{GRAPH}/me/calendars/cal-1/events")
    assert send.call_args.kwargs["json"] == {
        "subject": "Offsite",
        "body": {"contentType": "Text", "content": "Agenda"},
        "isAllDay": True,
        "start": {"dateTime": "2026-10-07T00:00:00", "timeZone": "Europe/Amsterdam"},
        "end": {"dateTime": "2026-10-08T00:00:00", "timeZone": "Europe/Amsterdam"},
        "attendees": [
            {"emailAddress": {"address": "a@example.com"}, "type": "required"}
        ],
    }
    assert result.data["is_all_day"] is True
    assert result.data["web_link"] == "https://outlook.office365.com/e1"


@pytest.mark.django_db
def test_outlook_calendar_update_and_delete(data_fixture):
    update = data_fixture.create_outlook_calendar_update_event_service(
        integration_args=connected(), event_id="'e1'", location="'Room 2'"
    )
    with patch(SEND, return_value=fake_response(200, {"id": "e1"})) as send:
        update.get_type().dispatch(update, FakeDispatchContext())
    assert send.call_args.args == ("PATCH", f"{GRAPH}/me/events/e1")
    assert send.call_args.kwargs["json"] == {"location": {"displayName": "Room 2"}}

    delete = data_fixture.create_outlook_calendar_delete_event_service(
        integration_args=connected(), event_id="'e1'"
    )
    with patch(SEND, return_value=fake_response(204)) as send:
        result = delete.get_type().dispatch(delete, FakeDispatchContext())
    assert send.call_args.args == ("DELETE", f"{GRAPH}/me/events/e1")
    assert result.data == {"event_id": "e1", "deleted": True}


@pytest.mark.django_db
def test_outlook_calendar_list_events_window_or_upcoming(data_fixture):
    windowed = data_fixture.create_outlook_calendar_list_events_service(
        integration_args=connected(),
        start="'2026-10-01T00:00:00'",
        end="'2026-10-31T00:00:00'",
        max_results=10,
    )
    body = {"value": [{"id": "e1", "subject": "A", "start": {}, "end": {}}]}
    with patch(SEND, return_value=fake_response(200, body)) as send:
        result = windowed.get_type().dispatch(windowed, FakeDispatchContext())
    assert send.call_args.args == ("GET", f"{GRAPH}/me/calendarView")
    assert send.call_args.kwargs["params"] == {
        "$top": 10,
        "$orderby": "start/dateTime",
        "startDateTime": "2026-10-01T00:00:00",
        "endDateTime": "2026-10-31T00:00:00",
    }
    assert result.data["count"] == 1

    upcoming = data_fixture.create_outlook_calendar_list_events_service(
        integration_args=connected(), calendar_id="'cal-1'"
    )
    with patch(SEND, return_value=fake_response(200, {"value": []})) as send:
        upcoming.get_type().dispatch(upcoming, FakeDispatchContext())
    assert send.call_args.args == ("GET", f"{GRAPH}/me/calendars/cal-1/events")

    half = data_fixture.create_outlook_calendar_list_events_service(
        integration_args=connected(), start="'2026-10-01T00:00:00'"
    )
    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        half.get_type().dispatch(half, FakeDispatchContext())


@pytest.mark.django_db
def test_microsoft_token_urls_follow_the_tenant(data_fixture):
    integration = data_fixture.create_microsoft_integration(tenant="contoso.com")
    integration_type = integration.get_type()
    assert integration_type.get_authorization_url(integration) == (
        "https://login.microsoftonline.com/contoso.com/oauth2/v2.0/authorize"
    )
    assert integration_type.get_token_url(integration) == (
        "https://login.microsoftonline.com/contoso.com/oauth2/v2.0/token"
    )
    assert (
        integration_type.extract_account_email({"userPrincipalName": "me@contoso.com"})
        == "me@contoso.com"
    )
