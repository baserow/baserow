import re

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from rest_framework import serializers

_HIGH_RISK_TLDS = (
    "com|net|org|io|co|info|biz|xyz|top|shop|site|online|link|club|app|dev|"
    "live|me|ly|to|cc|gd|ru|cn|de|uk|nl|tk|ml|ga|cf|gq|click|icu|buzz|pw|vip"
)
# Matches URL-like content: an explicit protocol, a `www.` prefix, a domain-like token
# with a high risk TLD (e.g. `evil.com`), or any domain-like token followed by a path
# (e.g. `x.gd/spam`). Dotted names like `J.Smith`, `Dr.Smith` do not match.
URL_LIKE_NAME_REGEX = re.compile(
    rf"https?://|www\.|[a-z0-9][a-z0-9-]*\.(?:{_HIGH_RISK_TLDS})\b|\S\.[a-zA-Z]{{2,}}/",
    re.IGNORECASE,
)
EMAIL_LIKE_NAME_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CONTROL_CHARS_REGEX = re.compile(r"[\x00-\x1f\x7f]")


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
