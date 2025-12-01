import json
import smtplib
import socket
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from baserow.contrib.integrations.core.service_types import CoreSMTPEmailServiceType
from baserow.core.services.exceptions import (
    InvalidContextContentDispatchException,
    ServiceImproperlyConfiguredDispatchException,
    UnexpectedDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.test_utils.helpers import AnyInt
from baserow.test_utils.pytest_conftest import FakeDispatchContext


@contextmanager
def mock_django_email(
    should_succeed=True,
    exception_class=None,
):
    """Context manager to mock SMTP connection behavior."""

    server_mock = MagicMock()
    server_mock.send.return_value = should_succeed

    if exception_class:
        if exception_class is ConnectionRefusedError:
            server_mock.send.side_effect = exception_class()
        elif exception_class == socket.gaierror:
            server_mock.send.side_effect = exception_class("Host not found")
        elif exception_class in [
            smtplib.SMTPNotSupportedError,
            smtplib.SMTPAuthenticationError,
            smtplib.SMTPConnectError,
        ]:
            server_mock.send.side_effect = exception_class(500, "Error message")
            server_mock.send.side_effect = exception_class(500, "Error message")
        else:
            server_mock.send.side_effect = exception_class("Generic error")

    with patch(
        "baserow.contrib.integrations.core.service_types.EmailMultiAlternatives",
        return_value=server_mock,
    ) as mock_email, patch(
        "baserow.contrib.integrations.core.service_types.get_connection",
    ) as mock_connection:
        yield (mock_email, mock_connection)


@pytest.mark.django_db
def test_send_smtp_email_basic(data_fixture):
    smtp_integration = data_fixture.create_smtp_integration(
        host="smtp.example.com",
        port=587,
        use_tls=True,
        username="user@example.com",
        password="password123",
    )

    service = data_fixture.create_core_smtp_email_service(
        integration=smtp_integration,
        from_email="'sender@example.com'",
        from_name="'Test Sender'",
        to_emails="'recipient@example.com'",
        subject="'Test Subject'",
        body="'Hello, this is a test email!'",
        body_type="plain",
    )

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    with mock_django_email() as (mock_email, mock_connection):
        result = service_type.dispatch(service, dispatch_context)
        mock_connection.assert_called_once_with(
            backend="django.core.mail.backends.smtp.EmailBackend",
            host="smtp.example.com",
            port=587,
            username="user@example.com",
            password="password123",
            use_tls=True,
        )
        mock_email.assert_called_once_with(
            "Test Subject",
            "Hello, this is a test email!",
            "Test Sender <sender@example.com>",
            ["recipient@example.com"],
            bcc=[],
            cc=[],
            connection=mock_connection.return_value,
        )
        assert mock_email.return_value.content_subtype == "plain"
        assert result.data == {"success": True}


@pytest.mark.django_db
def test_send_smtp_email_multiple_to_cc_and_bcc(data_fixture):
    smtp_integration = data_fixture.create_smtp_integration(
        host="smtp.example.com",
        port=587,
        use_tls=True,
        username="user@example.com",
        password="password123",
    )

    service = data_fixture.create_core_smtp_email_service(
        integration=smtp_integration,
        from_email="'sender@example.com'",
        from_name="'Test Sender'",
        to_emails="'recipient1@example.com,recipient2@example.com'",
        cc_emails="'cc1@example.com,cc2@example.com'",
        bcc_emails="'bcc1@example.com,bcc2@example.com'",
        subject="'Test Subject'",
        body="'<h1>Hello</h1><p>This is a test email!</p>'",
        body_type="html",
    )

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    with mock_django_email() as (mock_email, mock_connection):
        result = service_type.dispatch(service, dispatch_context)

        mock_email.assert_called_once_with(
            "Test Subject",
            "<h1>Hello</h1><p>This is a test email!</p>",
            "Test Sender <sender@example.com>",
            ["recipient1@example.com", "recipient2@example.com"],
            bcc=["bcc1@example.com", "bcc2@example.com"],
            cc=["cc1@example.com", "cc2@example.com"],
            connection=mock_connection.return_value,
        )
        assert mock_email.return_value.content_subtype == "html"
        assert result.data == {"success": True}


@pytest.mark.django_db
def test_send_smtp_email_tls_not_supported_error(data_fixture):
    smtp_integration = data_fixture.create_smtp_integration(
        host="smtp.example.com",
        port=587,
        use_tls=True,
    )

    service = data_fixture.create_core_smtp_email_service(
        integration=smtp_integration,
        from_email="'sender@example.com'",
        to_emails="'recipient@example.com'",
        subject="'Test Subject'",
        body="'Test body'",
    )

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc_info:
        with mock_django_email(exception_class=smtplib.SMTPNotSupportedError):
            service_type.dispatch(service, dispatch_context)

    assert str(exc_info.value) == "TLS not supported by server"


@pytest.mark.django_db
def test_send_smtp_email_host_could_not_be_reached_error(data_fixture):
    smtp_integration = data_fixture.create_smtp_integration(
        host="nonexistent.example.com",
        port=587,
    )

    service = data_fixture.create_core_smtp_email_service(
        integration=smtp_integration,
        from_email="'sender@example.com'",
        to_emails="'recipient@example.com'",
        subject="'Test Subject'",
        body="'Test body'",
    )

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc_info:
        with mock_django_email(exception_class=socket.gaierror):
            service_type.dispatch(service, dispatch_context)

    assert (
        str(exc_info.value)
        == "The host nonexistent.example.com:587 could not be reached"
    )


@pytest.mark.django_db
def test_send_smtp_email_connection_refused_error(data_fixture):
    smtp_integration = data_fixture.create_smtp_integration(
        host="smtp.example.com",
        port=587,
    )

    service = data_fixture.create_core_smtp_email_service(
        integration=smtp_integration,
        from_email="'sender@example.com'",
        to_emails="'recipient@example.com'",
        subject="'Test Subject'",
        body="'Test body'",
    )

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc_info:
        with mock_django_email(exception_class=ConnectionRefusedError):
            service_type.dispatch(service, dispatch_context)

    assert str(exc_info.value) == "Connection refused by smtp.example.com:587"


@pytest.mark.django_db
def test_send_smtp_email_username_password_incorrect_error(data_fixture):
    smtp_integration = data_fixture.create_smtp_integration(
        host="smtp.example.com",
        port=587,
        username="user@example.com",
        password="wrongpassword",
    )

    service = data_fixture.create_core_smtp_email_service(
        integration=smtp_integration,
        from_email="'sender@example.com'",
        to_emails="'recipient@example.com'",
        subject="'Test Subject'",
        body="'Test body'",
    )

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc_info:
        with mock_django_email(exception_class=smtplib.SMTPAuthenticationError):
            service_type.dispatch(service, dispatch_context)

    assert str(exc_info.value) == "The username or password is incorrect"


@pytest.mark.django_db
def test_send_smtp_email_unable_to_connect_to_the_smtp_server(data_fixture):
    smtp_integration = data_fixture.create_smtp_integration(
        host="smtp.example.com",
        port=587,
    )

    service = data_fixture.create_core_smtp_email_service(
        integration=smtp_integration,
        from_email="'sender@example.com'",
        to_emails="'recipient@example.com'",
        subject="'Test Subject'",
        body="'Test body'",
    )

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    with pytest.raises(UnexpectedDispatchException) as exc_info:
        with mock_django_email(exception_class=smtplib.SMTPConnectError):
            service_type.dispatch(service, dispatch_context)

    assert str(exc_info.value) == "Unable to connect to the SMTP server"


@pytest.mark.django_db
def test_send_smtp_email_with_formulas(data_fixture):
    smtp_integration = data_fixture.create_smtp_integration(
        host="smtp.example.com",
        port=587,
        use_tls=True,
        username="user@example.com",
        password="password123",
    )

    service = data_fixture.create_core_smtp_email_service(
        integration=smtp_integration,
        from_email="concat('sender', '@', get('domain'))",
        from_name="concat('Hello ', get('name'))",
        to_emails="concat(get('email'), ', admin@', get('domain'))",
        subject="concat('Welcome ', get('name'), '!')",
        body="concat('Hello ', get('name'), ', welcome to our service!')",
        body_type="plain",
    )

    service_type = service.get_type()

    formula_context = {
        "name": "John Doe",
        "email": "john@example.com",
        "domain": "example.com",
    }
    dispatch_context = FakeDispatchContext(context=formula_context)

    with mock_django_email() as (mock_email, mock_connection):
        service_type.dispatch(service, dispatch_context)
        mock_email.assert_called_once_with(
            "Welcome John Doe!",
            "Hello John Doe, welcome to our service!",
            "Hello John Doe <sender@example.com>",
            ["john@example.com", "admin@example.com"],
            bcc=[],
            cc=[],
            connection=mock_connection.return_value,
        )


@pytest.mark.django_db
def test_send_smtp_email_no_recipients_error(data_fixture):
    smtp_integration = data_fixture.create_smtp_integration(
        host="smtp.example.com",
        port=587,
    )

    service = data_fixture.create_core_smtp_email_service(
        integration=smtp_integration,
        from_email="'sender@example.com'",
        to_emails="''",
        subject="'Test Subject'",
        body="'Test body'",
    )

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    with pytest.raises(InvalidContextContentDispatchException) as exc_info:
        service_type.dispatch(service, dispatch_context)

    assert str(exc_info.value) == "At least one recipient email is required"


@pytest.mark.django_db
def test_smtp_email_service_generate_schema(data_fixture):
    smtp_integration = data_fixture.create_smtp_integration()

    service = data_fixture.create_core_smtp_email_service(
        integration=smtp_integration,
        from_email="'sender@example.com'",
        to_emails="'recipient@example.com'",
        subject="'Test Subject'",
        body="'Test body'",
    )

    service_type = service.get_type()
    schema = service_type.generate_schema(service)

    assert schema == {
        "title": f"SMTPEmail{service.id}Schema",
        "type": "object",
        "properties": {
            "success": {
                "type": "boolean",
                "title": "Success",
                "description": "Whether the email was sent successfully",
            }
        },
    }


@pytest.mark.django_db
def test_serialized_export_import(data_fixture):
    smtp_integration = data_fixture.create_smtp_integration(
        host="smtp.example.com",
        port=587,
        use_tls=True,
        username="user@example.com",
        password="password123",
    )

    service = data_fixture.create_core_smtp_email_service(
        integration=smtp_integration,
        from_email="'sender@example.com'",
        from_name="'Test Sender'",
        to_emails="'recipient@example.com'",
        cc_emails="'cc@example.com'",
        bcc_emails="'bcc@example.com'",
        subject="'Test Subject'",
        body="'Test body'",
        body_type="html",
    )

    service_type = service.get_type()

    serialized = json.loads(json.dumps(service_type.export_serialized(service)))

    expected_serialized = {
        "id": AnyInt(),
        "integration_id": smtp_integration.id,
        "sample_data": None,
        "type": "smtp_email",
        "from_email": {
            "formula": "'sender@example.com'",
            "mode": "simple",
            "version": "0.1",
        },
        "from_name": {"formula": "'Test Sender'", "mode": "simple", "version": "0.1"},
        "to_emails": {
            "formula": "'recipient@example.com'",
            "mode": "simple",
            "version": "0.1",
        },
        "cc_emails": {
            "formula": "'cc@example.com'",
            "mode": "simple",
            "version": "0.1",
        },
        "bcc_emails": {
            "formula": "'bcc@example.com'",
            "mode": "simple",
            "version": "0.1",
        },
        "subject": {"formula": "'Test Subject'", "mode": "simple", "version": "0.1"},
        "body_type": "html",
        "body": {"formula": "'Test body'", "mode": "simple", "version": "0.1"},
    }

    assert serialized == expected_serialized

    new_service = service_type.import_serialized(
        None, serialized, {smtp_integration.id: smtp_integration}, lambda x, d: x
    )

    assert new_service.from_email["formula"] == "'sender@example.com'"
    assert new_service.from_name["formula"] == "'Test Sender'"
    assert new_service.to_emails["formula"] == "'recipient@example.com'"
    assert new_service.cc_emails["formula"] == "'cc@example.com'"
    assert new_service.bcc_emails["formula"] == "'bcc@example.com'"
    assert new_service.subject["formula"] == "'Test Subject'"
    assert new_service.body_type == "html"
    assert new_service.body["formula"] == "'Test body'"


@pytest.mark.django_db
def test_smtp_email_service_create_update(data_fixture):
    smtp_integration = data_fixture.create_smtp_integration()

    service = ServiceHandler().create_service(
        CoreSMTPEmailServiceType(),
        integration_id=smtp_integration.id,
        from_email="'sender@example.com'",
        from_name="'Test Sender'",
        to_emails="'recipient@example.com'",
        subject="'Test Subject'",
        body="'Test body'",
        body_type="plain",
    )

    assert service.from_email == {
        "mode": "simple",
        "formula": "'sender@example.com'",
        "version": "0.1",
    }
    assert service.from_name == {
        "mode": "simple",
        "formula": "'Test Sender'",
        "version": "0.1",
    }
    assert service.to_emails == {
        "mode": "simple",
        "formula": "'recipient@example.com'",
        "version": "0.1",
    }
    assert service.subject == {
        "mode": "simple",
        "formula": "'Test Subject'",
        "version": "0.1",
    }
    assert service.body == {
        "mode": "simple",
        "formula": "'Test body'",
        "version": "0.1",
    }
    assert service.body_type == "plain"
    assert service.integration_id == smtp_integration.id

    service_type = service.get_type()
    ServiceHandler().update_service(
        service_type,
        service,
        from_email="'updated@example.com'",
        subject="'Updated Subject'",
        body_type="html",
    )

    service.refresh_from_db()

    assert service.from_email["formula"] == "'updated@example.com'"
    assert service.subject["formula"] == "'Updated Subject'"
    assert service.body["formula"] == "'Test body'"
    assert service.body_type == "html"
