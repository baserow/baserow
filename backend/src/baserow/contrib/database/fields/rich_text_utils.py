import re
from typing import Optional

from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler

MARKDOWN_IMAGE_REGEX = re.compile(
    r"!\[[^\[\]]*(?:\\.[^\[\]]*)*\]\[([a-zA-Z0-9]+_[a-zA-Z0-9]+\.\w+)\]"
)

MARKDOWN_IMAGE_WITH_URL_REGEX = re.compile(
    r"(!\[[^\[\]]*(?:\\.[^\[\]]*)*\]\[([a-zA-Z0-9]+_[a-zA-Z0-9]+\.\w+)\])\([^)]+\)"
)


def extract_user_file_names(content: Optional[str]) -> set[str]:
    """
    Extract UserFile names from markdown image syntax ``![alt][filename]``.

    :param content: Markdown text that may contain image references.
    :return: Set of UserFile name strings found in the content.
    """

    if not content:
        return set()

    return set(MARKDOWN_IMAGE_REGEX.findall(content))


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
        name = match.group(1)
        url = url_map.get(name)
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

    return MARKDOWN_IMAGE_WITH_URL_REGEX.sub(r"\1", content)
