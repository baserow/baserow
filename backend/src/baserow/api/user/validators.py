import re

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from rest_framework import serializers

# Matches URL-like content: an explicit protocol, a `www.` prefix, or a
# domain-like token (a non-space character followed by a dot and two or more
# letters, e.g. `evil.com`). A dot followed by a space or a single letter, as
# in `Dr. Smith` or `J.R.R. Tolkien`, does not match.
URL_LIKE_NAME_REGEX = re.compile(r"https?://|www\.|\S\.[a-zA-Z]{2,}", re.IGNORECASE)
CONTROL_CHARS_REGEX = re.compile(r"[\x00-\x1f\x7f]")


def name_validation(value):
    """
    Rejects names containing URL-like content or control characters to prevent
    abuse of transactional emails for phishing.
    """

    if CONTROL_CHARS_REGEX.search(value) or URL_LIKE_NAME_REGEX.search(value):
        raise serializers.ValidationError(
            "Names can't contain URLs, domains or control characters.",
            code="invalid_name",
        )

    return value


def password_validation(value):
    """
    Verifies that the provided password adheres to the password validation as defined
    in the django core settings.
    """

    try:
        validate_password(value)
    except ValidationError as e:
        raise serializers.ValidationError(
            e.messages[0], code="password_validation_failed"
        )

    return value


def language_validation(value):
    """
    Verifies that the provided language is known.
    """

    valid_languages = [lang[0] for lang in settings.LANGUAGES]
    if value not in valid_languages:
        raise serializers.ValidationError(
            f"Only the following language keys are valid: {','.join(valid_languages)}",
            code="invalid_language",
        )

    return value
