"""Public tool failures and optional builder diagnostics for configured agent actions."""

import socket
import ssl
from smtplib import (
    SMTPAuthenticationError,
    SMTPConnectError,
    SMTPDataError,
    SMTPNotSupportedError,
    SMTPRecipientsRefused,
    SMTPSenderRefused,
    SMTPServerDisconnected,
)

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from baserow.contrib.database.fields.exceptions import FieldDataConstraintException
from baserow.contrib.database.rows.exceptions import RowDoesNotExist
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.contrib.integrations.slack.constants import (
    SLACK_INVALID_AUTH,
    SLACK_NO_TEXT,
)
from baserow.core.embeddings import EmbeddingsServiceError
from baserow.core.services.exceptions import (
    AddressNotAllowedDispatchException,
    DispatchException,
    InvalidContextContentDispatchException,
    InvalidContextDispatchException,
    PermissionDeniedDispatchException,
    RemoteBusyDispatchException,
    RemoteRefusedDispatchException,
    ResponseTooLargeDispatchException,
    RuntimeDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.tools.errors import NOT_FOUND_MESSAGE, ToolError, ToolErrorCode

EMAIL_CONNECTION_ERROR = ToolError(
    ToolErrorCode.INVALID_INPUT, "Could not connect to the email service."
)
EMAIL_DELIVERY_UNCONFIRMED = ToolError(
    ToolErrorCode.FAILED, "The email service did not confirm delivery."
)
SMTP_TIMEOUT_DIAGNOSIS = "The SMTP server did not answer before the timeout."
SMTP_DNS_DIAGNOSIS = "The SMTP host could not be resolved."
SMTP_REFUSED_DIAGNOSIS = "The SMTP server refused the connection."
EMAIL_AUTH_ERROR = ToolError(
    ToolErrorCode.INVALID_INPUT,
    "The email service rejected its credentials. Ask an agent builder to check the connection.",
)
EMAIL_UNSUPPORTED_ERROR = ToolError(
    ToolErrorCode.INVALID_INPUT,
    "The email service does not support a required feature. Ask an agent builder to check authentication and TLS.",
)

_SMTP_FAILURES = {
    socket.gaierror: (EMAIL_CONNECTION_ERROR, SMTP_DNS_DIAGNOSIS),
    ConnectionRefusedError: (EMAIL_CONNECTION_ERROR, SMTP_REFUSED_DIAGNOSIS),
    SMTPAuthenticationError: (EMAIL_AUTH_ERROR, None),
    SMTPNotSupportedError: (EMAIL_UNSUPPORTED_ERROR, None),
    ssl.SSLCertVerificationError: (
        ToolError(
            ToolErrorCode.INVALID_INPUT,
            "The email service certificate could not be verified.",
        ),
        None,
    ),
    SMTPConnectError: (
        ToolError(ToolErrorCode.FAILED, "The email service declined the connection."),
        None,
    ),
    TimeoutError: (EMAIL_DELIVERY_UNCONFIRMED, SMTP_TIMEOUT_DIAGNOSIS),
    SMTPServerDisconnected: (
        EMAIL_DELIVERY_UNCONFIRMED,
        "The SMTP server closed the connection.",
    ),
    SMTPRecipientsRefused: (
        ToolError(
            ToolErrorCode.INVALID_INPUT, "The email service rejected the recipients."
        ),
        None,
    ),
    SMTPSenderRefused: (
        ToolError(
            ToolErrorCode.INVALID_INPUT, "The email service rejected the sender."
        ),
        None,
    ),
    SMTPDataError: (
        ToolError(ToolErrorCode.FAILED, "The email service rejected the message."),
        None,
    ),
}


# More specific dispatch types must precede their configuration and runtime parents.
_DISPATCH_ERRORS = {
    PermissionDeniedDispatchException: ToolError(
        ToolErrorCode.PERMISSION_DENIED,
        "The agent does not have permission to perform this action.",
    ),
    RemoteBusyDispatchException: ToolError(
        ToolErrorCode.FAILED, "The service is busy. Try again later."
    ),
    RemoteRefusedDispatchException: ToolError(
        ToolErrorCode.FAILED, "The service declined the request."
    ),
    ResponseTooLargeDispatchException: ToolError(
        ToolErrorCode.FAILED, "The service response was too large."
    ),
    AddressNotAllowedDispatchException: ToolError(
        ToolErrorCode.INVALID_INPUT,
        "The configured address cannot be used by this action.",
    ),
    RuntimeDispatchException: ToolError(
        ToolErrorCode.FAILED, "The service did not complete the request."
    ),
    ServiceImproperlyConfiguredDispatchException: ToolError(
        ToolErrorCode.INVALID_INPUT,
        "Ask an agent builder to check the action configuration.",
    ),
    InvalidContextDispatchException: ToolError(
        ToolErrorCode.INVALID_INPUT, "The action could not resolve its inputs."
    ),
    InvalidContextContentDispatchException: ToolError(
        ToolErrorCode.INVALID_INPUT, "One or more action inputs are invalid."
    ),
}
_CAUSE_ERRORS = {
    (RowDoesNotExist, TableDoesNotExist): ToolError(
        ToolErrorCode.NOT_FOUND, NOT_FOUND_MESSAGE
    ),
    FieldDataConstraintException: ToolError(
        ToolErrorCode.INVALID_INPUT, "A row value violates a field constraint."
    ),
    EmbeddingsServiceError: ToolError(
        ToolErrorCode.FAILED, "Semantic search is temporarily unavailable."
    ),
}


def classify_action_failure(
    action_type: str, exc: DispatchException
) -> tuple[ToolError, str | None]:
    """Only return messages safe for the agent audience, including the model."""
    cause = exc.__cause__
    if action_type == "smtp_email":
        if (
            isinstance(cause, ValidationError)
            and getattr(cause, "message", None) == validate_email.message
        ):
            return ToolError(
                ToolErrorCode.INVALID_INPUT, str(validate_email.message)
            ), None
        for cause_type, failure in _SMTP_FAILURES.items():
            if isinstance(cause, cause_type):
                return failure
    if action_type == "slack_write_message" and isinstance(
        exc, RemoteRefusedDispatchException
    ):
        for message in (SLACK_INVALID_AUTH, SLACK_NO_TEXT):
            if exc.args == (message,):
                return ToolError(ToolErrorCode.INVALID_INPUT, message), None
    for cause_type, error in _CAUSE_ERRORS.items():
        if isinstance(cause, cause_type):
            return error, None
    for dispatch_type, error in _DISPATCH_ERRORS.items():
        if isinstance(exc, dispatch_type):
            return error, None
    return ToolError(ToolErrorCode.FAILED, None), None
