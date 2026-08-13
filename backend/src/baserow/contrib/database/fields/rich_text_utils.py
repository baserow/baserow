import re
from typing import Optional

from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler

# Bounds the validation query, the URL resolution on every read and the files
# packed into an export for one cell.
MAX_RICH_TEXT_IMAGES = 100

# Embeddable even though the upload handler flags them ``is_image=False``: SVGs
# are active content when opened directly, but an ``<img>`` context never executes
# scripts or loads external resources. See the CSP headers on ``/media/``.
RENDERABLE_NON_IMAGE_EXTENSIONS = {"svg", "svgz"}

# Both classes exclude the backslash so ``\\.`` escapes match unambiguously (no
# catastrophic backtracking). The name class also rejects path separators, so a
# stored name can never become a storage path traversal.
_ALT_PATTERN = r"[^\[\]\\]*(?:\\.[^\[\]\\]*)*"
_NAME_PATTERN = r"[a-zA-Z0-9]+_[a-zA-Z0-9]+\.[^\]\s/\\]+"

# ``![alt][name]`` — the storage format of a Baserow user file image.
MARKDOWN_IMAGE_REGEX = re.compile(
    rf"!\[(?P<alt>{_ALT_PATTERN})\]\[(?P<name>{_NAME_PATTERN})\]"
)

# ``![alt][name](url)`` — the API format with the resolved storage URL appended.
MARKDOWN_IMAGE_WITH_URL_REGEX = re.compile(
    rf"(?P<ref>!\[(?P<alt>{_ALT_PATTERN})\]\[(?P<name>{_NAME_PATTERN})\])"
    r"\((?P<url>[^)]+)\)"
)

# ``![alt](url)`` — a plain markdown image (external URL, not a Baserow upload).
# Cannot match the Baserow forms above because there ``]`` is followed by
# ``[name]`` rather than ``(``.
MARKDOWN_PLAIN_IMAGE_REGEX = re.compile(
    rf"!\[(?P<alt>{_ALT_PATTERN})\]\((?P<url>[^)]*)\)"
)

_ESCAPED_BRACKET_REGEX = re.compile(r"\\([\[\]])")

# Schemes a plain ``![alt](url)`` image may use. Empty means a relative URL.
_SAFE_IMAGE_SCHEMES = {"http", "https", ""}


def extract_user_file_names(content: Optional[str]) -> set[str]:
    """
    Extract UserFile names from markdown image syntax ``![alt][filename]``.

    :param content: Markdown text that may contain image references.
    :return: Set of UserFile name strings found in the content.
    """

    if not content:
        return set()

    return {match.group("name") for match in MARKDOWN_IMAGE_REGEX.finditer(content)}


def count_image_references(content: Optional[str]) -> int:
    """
    Count image references in ``content``, including repeats of the same name.

    ``extract_user_file_names`` collapses duplicates, so it cannot bound how many
    ``<img>`` nodes a client renders for one cell.

    :param content: Markdown text that may contain image references.
    :return: The number of ``![alt][name]`` references in the content.
    """

    if not content:
        return 0

    return sum(1 for _ in MARKDOWN_IMAGE_REGEX.finditer(content))


def resolve_user_file_urls(names: set[str]) -> dict[str, str]:
    """
    Resolve UserFile names to current storage URLs via pure path
    computation. No DB query — matches the FileField URL resolution
    pattern.

    :param names: Set of UserFile name strings to resolve.
    :return: Mapping of ``{user_file_name: url_string}``.
    """

    if not names:
        return {}

    handler = UserFileHandler()
    storage = get_default_storage()
    return {name: storage.url(handler.user_file_path(name)) for name in names}


def append_user_file_urls(content: Optional[str]) -> str:
    """
    Transform ``![alt][name]`` patterns into ``![alt][name](url)`` by
    appending resolved storage URLs inline.

    Already-resolved patterns ``![alt][name](url)`` are re-resolved
    with fresh URLs (handles signed URL expiry).

    :param content: Markdown text that may contain image references.
    :return: Content with resolved URLs appended to image references.
    """

    if not content:
        return content or ""

    content = strip_user_file_urls(content)

    names = extract_user_file_names(content)
    if not names:
        return content

    url_map = resolve_user_file_urls(names)

    def _replace(match):
        url = url_map.get(match.group("name"))
        if url:
            return f"{match.group(0)}({url})"
        return match.group(0)

    return MARKDOWN_IMAGE_REGEX.sub(_replace, content)


def strip_user_file_urls(content: Optional[str]) -> str:
    """
    Strip resolved URLs from ``![alt][name](url)`` patterns, returning
    the DB-storage format ``![alt][name]``.

    :param content: Markdown text that may contain resolved image URLs.
    :return: Content with URLs stripped from image references.
    """

    if not content:
        return content or ""

    return MARKDOWN_IMAGE_WITH_URL_REGEX.sub(r"\g<ref>", content)


def validate_external_image_protocols(content: Optional[str]) -> str:
    """
    Ensure plain markdown images ``![alt](url)`` use safe protocols.

    Images with ``http``, ``https`` or empty (relative) URLs pass through.
    Anything else (``javascript:``, ``data:``, etc.) is rewritten into a link
    ``[alt](url)`` so the browser never auto-loads it.

    :param content: Markdown text that may contain plain image syntax.
    :return: Content with unsafe-protocol images converted to links.
    """

    if not content:
        return content or ""

    def _check(match):
        url = match.group("url").strip()
        scheme = url.split(":", 1)[0].lower() if ":" in url else ""
        if scheme in _SAFE_IMAGE_SCHEMES:
            return match.group(0)
        return f"[{match.group('alt')}]({match.group('url')})"

    return MARKDOWN_PLAIN_IMAGE_REGEX.sub(_check, content)


def replace_user_file_images_with_alt(content: Optional[str]) -> str:
    """
    Replace all image references — ``![alt][name]``, ``![alt][name](url)``
    and ``![alt](url)`` — with their alt text, producing a plain text
    representation of the content.

    :param content: Markdown text that may contain image references.
    :return: Content with image references replaced by their alt text.
    """

    if not content:
        return content or ""

    def _alt(match):
        return _ESCAPED_BRACKET_REGEX.sub(r"\1", match.group("alt"))

    content = MARKDOWN_IMAGE_WITH_URL_REGEX.sub(_alt, content)
    content = MARKDOWN_IMAGE_REGEX.sub(_alt, content)
    return MARKDOWN_PLAIN_IMAGE_REGEX.sub(_alt, content)


def keep_first_image_references(content: Optional[str], limit: int) -> str:
    """
    Keep the first ``limit`` ``![alt][name]`` references and replace every later
    one with its alt text. Counts occurrences, not distinct names.

    :param content: Markdown text that may contain image references.
    :param limit: How many references to keep.
    :return: The content with the surplus references replaced by their alt text.
    """

    if not content:
        return content or ""

    kept = 0

    def _trim(match):
        nonlocal kept
        if kept < limit:
            kept += 1
            return match.group(0)
        return _ESCAPED_BRACKET_REGEX.sub(r"\1", match.group("alt"))

    return MARKDOWN_IMAGE_REGEX.sub(_trim, content)


def is_renderable_user_file(user_file) -> bool:
    """
    Whether the given user file may be embedded as an image in a rich text cell.

    :param user_file: A ``UserFile`` instance.
    :return: True if the file is an image or an SVG.
    """

    return bool(user_file.is_image) or (
        (user_file.original_extension or "").lower() in RENDERABLE_NON_IMAGE_EXTENSIONS
    )
