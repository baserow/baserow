from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from rest_framework import serializers

from baserow.api.validators import EMAIL_LIKE_NAME_REGEX, no_url_validation


def name_validation(value):
    """
    Rejects names containing URL-like content or control characters to prevent
    abuse of transactional emails for phishing, and email addresses because
    they're not a name.
    """

    if EMAIL_LIKE_NAME_REGEX.match(value):
        raise serializers.ValidationError(
            "Please enter your name, not your email address.",
            code="name_is_email",
        )

    return no_url_validation(value)


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
