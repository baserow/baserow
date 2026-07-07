import re

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


def no_url_validation(value):
    """
    Rejects values containing URL-like content or control characters to prevent abuse
    of transactional emails for phishing, because user provided names can end up in
    emails sent to others.
    """

    if CONTROL_CHARS_REGEX.search(value) or URL_LIKE_NAME_REGEX.search(value):
        raise serializers.ValidationError(
            "Names can't contain links, domains or web addresses.",
            code="invalid_name",
        )

    return value
