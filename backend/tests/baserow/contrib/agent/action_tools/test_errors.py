from smtplib import SMTPRecipientsRefused

import pytest

from baserow.contrib.agent.action_tools.errors import classify_action_failure
from baserow.contrib.database.fields.exceptions import FieldDataConstraintException
from baserow.contrib.integrations.slack.constants import (
    SLACK_INVALID_AUTH,
    SLACK_NO_TEXT,
)
from baserow.core.embeddings import EmbeddingsServiceError
from baserow.core.services.exceptions import (
    InvalidContextContentDispatchException,
    PermissionDeniedDispatchException,
    RemoteBusyDispatchException,
    RemoteRefusedDispatchException,
    UnexpectedDispatchException,
)
from baserow.core.tools.errors import ToolErrorCode


@pytest.mark.parametrize(
    "action,exception,message,cause,code,expected",
    [
        (
            "slack_write_message",
            RemoteRefusedDispatchException,
            SLACK_INVALID_AUTH,
            None,
            ToolErrorCode.INVALID_INPUT,
            SLACK_INVALID_AUTH,
        ),
        (
            "slack_write_message",
            RemoteRefusedDispatchException,
            SLACK_NO_TEXT,
            None,
            ToolErrorCode.INVALID_INPUT,
            SLACK_NO_TEXT,
        ),
        (
            "slack_write_message",
            RemoteRefusedDispatchException,
            "PRIVATE_CHANNEL",
            None,
            ToolErrorCode.FAILED,
            "declined",
        ),
        (
            "slack_write_message",
            RemoteBusyDispatchException,
            "PRIVATE_CHANNEL",
            None,
            ToolErrorCode.FAILED,
            "busy",
        ),
        (
            "local_baserow_create_row",
            PermissionDeniedDispatchException,
            "PRIVATE_FIELD",
            None,
            ToolErrorCode.PERMISSION_DENIED,
            "permission",
        ),
        (
            "local_baserow_update_row",
            InvalidContextContentDispatchException,
            "PRIVATE_ROW",
            FieldDataConstraintException,
            ToolErrorCode.INVALID_INPUT,
            "constraint",
        ),
        (
            "local_baserow_semantic_search",
            UnexpectedDispatchException,
            "PRIVATE_ENDPOINT",
            EmbeddingsServiceError,
            ToolErrorCode.FAILED,
            "temporarily unavailable",
        ),
        (
            "smtp_email",
            UnexpectedDispatchException,
            "PRIVATE_ADDRESS",
            SMTPRecipientsRefused,
            ToolErrorCode.INVALID_INPUT,
            "recipients",
        ),
    ],
)
def test_agent_action_failure_only_explains_known_causes(
    action, exception, message, cause, code, expected
):
    failure = exception(message)
    if cause:
        failure.__cause__ = cause("PRIVATE_DETAIL")
    error, diagnosis = classify_action_failure(action, failure)
    assert error.code == code
    assert expected in error.message
    assert "PRIVATE" not in error.message
    assert diagnosis is None
    assert str(failure) == message
