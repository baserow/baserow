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

from baserow.core.services.exceptions import DispatchException
from baserow.core.tools.errors import ToolError, ToolErrorCode

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
EMAIL_TLS_ERROR = ToolError(
    ToolErrorCode.INVALID_INPUT,
    "The email service does not support the configured TLS settings.",
)
EMAIL_ADDRESS_ERROR = ToolError(
    ToolErrorCode.INVALID_INPUT, "Enter a valid email address."
)

_SMTP_FAILURES = {
    socket.gaierror: (EMAIL_CONNECTION_ERROR, SMTP_DNS_DIAGNOSIS),
    ConnectionRefusedError: (EMAIL_CONNECTION_ERROR, SMTP_REFUSED_DIAGNOSIS),
    SMTPAuthenticationError: (EMAIL_AUTH_ERROR, None),
    SMTPNotSupportedError: (EMAIL_TLS_ERROR, None),
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
            return EMAIL_ADDRESS_ERROR, None
        for cause_type, failure in _SMTP_FAILURES.items():
            if isinstance(cause, cause_type):
                return failure
    return ToolError(ToolErrorCode.FAILED, None), None
