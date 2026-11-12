from rest_framework.exceptions import ValidationError

AGENT_TEXT_MAX_LENGTH = 100000
AGENT_REJECTION_REASON_MAX_LENGTH = 1000


def validate_message_content(content: str) -> None:
    """
    Check message content for direct service and action calls, like the API does.

    :param content: The message content to check.
    :raises ValidationError: When the content isn't a string, is blank or is too
        long.
    """

    if not isinstance(content, str) or not content.strip():
        raise ValidationError({"content": "This field may not be blank."})
    if len(content) > AGENT_TEXT_MAX_LENGTH:
        raise ValidationError({"content": "The message is too long."})
