import base64
from datetime import timedelta
from email import message_from_bytes
from unittest.mock import patch

from django.utils import timezone

import pytest

from baserow.core.services.exceptions import (
    RemoteRefusedDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.test_utils.pytest_conftest import FakeDispatchContext
from tests.baserow.contrib.integrations.external_api_test_utils import fake_response

SEND = "baserow.contrib.integrations.external_api.send_http_request"


def connected():
    return {
        "access_token": "google-at",
        "access_token_expires_at": timezone.now() + timedelta(hours=1),
    }


@pytest.mark.django_db
def test_gmail_send_email_builds_a_raw_message(data_fixture):
    service = data_fixture.create_gmail_send_email_service(
        integration_args=connected(),
        to_emails="'a@example.com; b@example.com'",
        cc_emails="'c@example.com'",
        subject="'Hello'",
        body="'Line one\nLine two'",
    )
    with patch(
        SEND, return_value=fake_response(200, {"id": "m1", "threadId": "t1"})
    ) as send:
        result = service.get_type().dispatch(service, FakeDispatchContext())

    assert result.data == {"id": "m1", "thread_id": "t1"}
    assert send.call_args.args == (
        "POST",
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
    )
    assert send.call_args.kwargs["headers"] == {"Authorization": "Bearer google-at"}
    assert send.call_args.kwargs["allow_redirects"] is False
    raw = send.call_args.kwargs["json"]["raw"]
    message = message_from_bytes(base64.urlsafe_b64decode(raw))
    assert message["To"] == "a@example.com, b@example.com"
    assert message["Cc"] == "c@example.com"
    assert message["Bcc"] is None
    assert message["Subject"] == "Hello"
    assert message.get_payload().strip() == "Line one\nLine two"


@pytest.mark.django_db
def test_gmail_send_email_needs_a_recipient_and_a_connected_account(data_fixture):
    service = data_fixture.create_gmail_send_email_service(
        integration_args=connected(), to_emails="''"
    )
    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        service.get_type().dispatch(service, FakeDispatchContext())

    service = data_fixture.create_gmail_send_email_service(
        integration_args={"refresh_token": ""}, to_emails="'a@example.com'"
    )
    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        service.get_type().dispatch(service, FakeDispatchContext())
    assert "not connected" in str(exc.value)


@pytest.mark.django_db
def test_google_refusal_carries_its_message_and_a_reconnect_hint(data_fixture):
    service = data_fixture.create_gmail_send_email_service(
        integration_args=connected(), to_emails="'a@example.com'"
    )
    body = {"error": {"code": 401, "message": "Invalid Credentials"}}
    with patch(SEND, return_value=fake_response(401, body)):
        with pytest.raises(RemoteRefusedDispatchException) as exc:
            service.get_type().dispatch(service, FakeDispatchContext())
    assert str(exc.value) == (
        "Google answered 401: Invalid Credentials. Check the credentials of the "
        "integration and reconnect it."
    )


@pytest.mark.django_db
def test_google_calendar_create_event_timed_and_all_day(data_fixture):
    service = data_fixture.create_google_calendar_create_event_service(
        integration_args=connected(),
        calendar_id="'team@group.calendar.google.com'",
        summary="'Standup'",
        start="'2026-10-07T09:00:00'",
        end="'2026-10-07T09:15:00'",
        time_zone="'Europe/Amsterdam'",
        attendees="'a@example.com, b@example.com'",
    )
    event = {
        "id": "e1",
        "summary": "Standup",
        "status": "confirmed",
        "htmlLink": "https://calendar.google.com/e1",
        "start": {"dateTime": "2026-10-07T09:00:00+02:00"},
        "end": {"dateTime": "2026-10-07T09:15:00+02:00"},
        "attendees": [{"email": "a@example.com"}, {"email": "b@example.com"}],
    }
    with patch(SEND, return_value=fake_response(200, event)) as send:
        result = service.get_type().dispatch(service, FakeDispatchContext())

    assert send.call_args.args == (
        "POST",
        "https://www.googleapis.com/calendar/v3/calendars/"
        "team%40group.calendar.google.com/events",
    )
    assert send.call_args.kwargs["json"] == {
        "summary": "Standup",
        "start": {"dateTime": "2026-10-07T09:00:00", "timeZone": "Europe/Amsterdam"},
        "end": {"dateTime": "2026-10-07T09:15:00", "timeZone": "Europe/Amsterdam"},
        "attendees": [{"email": "a@example.com"}, {"email": "b@example.com"}],
    }
    assert result.data["id"] == "e1"
    assert result.data["start"] == "2026-10-07T09:00:00+02:00"
    assert result.data["attendees"] == "a@example.com, b@example.com"

    all_day = data_fixture.create_google_calendar_create_event_service(
        integration_args=connected(),
        summary="'Offsite'",
        start="'2026-10-07'",
        end="'2026-10-08'",
    )
    with patch(SEND, return_value=fake_response(200, {"id": "e2"})) as send:
        all_day.get_type().dispatch(all_day, FakeDispatchContext())
    assert send.call_args.args[1].endswith("/calendars/primary/events")
    assert send.call_args.kwargs["json"]["start"] == {"date": "2026-10-07"}
    assert send.call_args.kwargs["json"]["end"] == {"date": "2026-10-08"}

    missing_end = data_fixture.create_google_calendar_create_event_service(
        integration_args=connected(), summary="'x'", start="'2026-10-07'"
    )
    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        missing_end.get_type().dispatch(missing_end, FakeDispatchContext())


@pytest.mark.django_db
def test_google_calendar_update_and_delete_event(data_fixture):
    update = data_fixture.create_google_calendar_update_event_service(
        integration_args=connected(), event_id="'e1'", location="'Room 2'"
    )
    with patch(SEND, return_value=fake_response(200, {"id": "e1"})) as send:
        update.get_type().dispatch(update, FakeDispatchContext())
    assert send.call_args.args == (
        "PATCH",
        "https://www.googleapis.com/calendar/v3/calendars/primary/events/e1",
    )
    assert send.call_args.kwargs["json"] == {"location": "Room 2"}

    nothing = data_fixture.create_google_calendar_update_event_service(
        integration_args=connected(), event_id="'e1'"
    )
    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        nothing.get_type().dispatch(nothing, FakeDispatchContext())

    delete = data_fixture.create_google_calendar_delete_event_service(
        integration_args=connected(), event_id="'e1'"
    )
    with patch(SEND, return_value=fake_response(204)) as send:
        result = delete.get_type().dispatch(delete, FakeDispatchContext())
    assert send.call_args.args[0] == "DELETE"
    assert result.data == {"event_id": "e1", "deleted": True}


@pytest.mark.django_db
def test_google_calendar_list_events(data_fixture):
    service = data_fixture.create_google_calendar_list_events_service(
        integration_args=connected(),
        time_min="'2026-10-01T00:00:00Z'",
        query="'standup'",
        max_results=500,
    )
    body = {
        "items": [
            {"id": "e1", "summary": "A", "start": {"date": "2026-10-02"}, "end": {}},
            {"id": "e2", "summary": "B", "start": {}, "end": {}},
        ]
    }
    with patch(SEND, return_value=fake_response(200, body)) as send:
        result = service.get_type().dispatch(service, FakeDispatchContext())

    assert send.call_args.args[0] == "GET"
    assert send.call_args.kwargs["params"] == {
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 250,
        "timeMin": "2026-10-01T00:00:00Z",
        "q": "standup",
    }
    assert result.data["count"] == 2
    assert result.data["events"][0]["start"] == "2026-10-02"
    schema = service.get_type().generate_schema(service)
    assert set(schema["properties"]) == {"events", "count"}
    assert "html_link" in schema["properties"]["events"]["items"]["properties"]


@pytest.mark.django_db
def test_google_service_export_import_keeps_formulas(data_fixture):
    service = data_fixture.create_gmail_send_email_service(
        to_emails="'a@example.com'", subject="'Hi'"
    )
    service_type = service.get_type()
    exported = service_type.export_serialized(service)
    assert exported["to_emails"]["formula"] == "'a@example.com'"
    assert exported["subject"]["formula"] == "'Hi'"
    imported = service_type.import_serialized(
        service.integration, exported, {}, import_formula=lambda f, m: f
    )
    assert imported.to_emails["formula"] == "'a@example.com'"
    assert imported.subject["formula"] == "'Hi'"
