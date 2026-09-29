import re
import unicodedata

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
# Decorative letters and digits (circled, negative circled, squared, sub/superscript
# and mathematical alphanumerics). Spammers use them to spell out contact details
# while evading filters, and they never occur in real names. Regional indicators
# (flag emoji) are deliberately excluded from the enclosed alphanumeric supplement.
STYLIZED_CHARS_REGEX = re.compile(
    "["
    "\u2070-\u209f"  # superscripts and subscripts
    "\u2460-\u24ff"  # enclosed alphanumerics
    "\u2776-\u2793"  # dingbat circled digits
    "\u3251-\u32bf"  # enclosed CJK numbers 21-50
    "\U0001d400-\U0001d7ff"  # mathematical alphanumeric symbols
    "\U0001f100-\U0001f1e5"  # enclosed alphanumeric supplement
    "]"
)
# Contact IDs (QQ, WhatsApp, phone numbers) embedded in a name to advertise them via
# transactional emails. Short numbers like `Team 2026` or `2025-2026` stay allowed.
LONG_DIGIT_RUN_REGEX = re.compile(r"\d{6,}")


def _normalize_name(value: str) -> str:
    """
    NFKC folds lookalike characters (fullwidth, sub/superscript, mathematical
    letters) into their ASCII form, and invisible format characters (zero-width
    spaces, joiners, bidi controls) are stripped because they can be inserted
    between digits or letters to break up a pattern without changing how the name
    renders. They're stripped rather than rejected because zero-width joiners are
    legitimate in emoji sequences and some scripts.
    """

    normalized = unicodedata.normalize("NFKC", value)
    return "".join(c for c in normalized if unicodedata.category(c) != "Cf")


def no_url_validation(value):
    """
    Rejects values containing URL-like content or control characters to prevent abuse
    of transactional emails for phishing, because user provided names can end up in
    emails sent to others.
    """

    normalized = _normalize_name(value)

    if CONTROL_CHARS_REGEX.search(value) or URL_LIKE_NAME_REGEX.search(normalized):
        raise serializers.ValidationError(
            "Names can't contain links, domains or web addresses.",
            code="invalid_name",
        )

    return value


def no_spam_validation(value):
    """
    Rejects values containing decorative characters or long numbers, because spam
    accounts use them to spell out contact details in names that end up in
    invitation emails.
    """

    normalized = _normalize_name(value)

    if STYLIZED_CHARS_REGEX.search(value) or LONG_DIGIT_RUN_REGEX.search(normalized):
        raise serializers.ValidationError(
            "Names can't contain decorative characters or long numbers.",
            code="invalid_name",
        )

    return value
