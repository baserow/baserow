import re
from typing import Callable, Container, Iterator, Optional

from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler

# Bounds the validation query, the URL resolution on every read and the files
# packed into an export for one cell.
MAX_RICH_TEXT_IMAGES = 100

# Embeddable even though the upload handler flags them ``is_image=False``: SVGs
# are active content when opened directly, but an ``<img>`` context never executes
# scripts or loads external resources. See the CSP headers on ``/media/``.
RENDERABLE_NON_IMAGE_EXTENSIONS = {"svg", "svgz"}

# Mirrored in richTextImageUtils.js, ASCII-only because ``\s`` and ``.`` differ in JS.
_WHITESPACE = r" \t\n\r\f\v"
# The backslash is excluded so escapes match unambiguously (no catastrophic backtracking).
_ALT_PATTERN = r"[^\[\]\\]*(?:\\[^\n][^\[\]\\]*)*"
# No path separators (storage traversal) and no ``)`` (it would end the URL early).
_NAME_PATTERN = rf"[a-zA-Z0-9]+_[a-zA-Z0-9]+\.[^\]{_WHITESPACE}/\\()]*"

# ``![alt][name]`` — the storage format of a Baserow user file image.
MARKDOWN_IMAGE_REGEX = re.compile(
    rf"!\[(?P<alt>{_ALT_PATTERN})\]\[(?P<name>{_NAME_PATTERN})\]"
)

# ``![alt][name](url)``, the API format; no ``(`` in the URL keeps failed matches linear.
MARKDOWN_IMAGE_WITH_URL_REGEX = re.compile(
    rf"(?P<ref>!\[(?P<alt>{_ALT_PATTERN})\]\[(?P<name>{_NAME_PATTERN})\])"
    rf"\((?P<url>[^(){_WHITESPACE}]*)\)"
)

_ESCAPED_BRACKET_REGEX = re.compile(r"\\([\[\]])")

# CommonMark 4.5: a fence is 3+ backticks or tildes indented by up to 3 spaces.
_FENCE_REGEX = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_FENCE_CLOSE_TAIL_REGEX = re.compile(r"[ \t]*\r?\n?")
_LINE_REGEX = re.compile(r"[^\n]*\n|[^\n]+\Z")
_BACKTICK_RUN_REGEX = re.compile(r"`+")


def _iter_fence_segments(content: str) -> Iterator[tuple[str, bool]]:
    """
    Splits ``content`` into fenced code blocks and the text around them. The
    fence lines belong to the code segment. An unclosed fence runs to the end.

    Lines end at ``\\n`` only, like the frontend: ``str.splitlines`` also breaks
    on ``\\r``, ``\\x1c`` or ``\\u2028``, and the two sides must agree on what
    is code.
    """

    text: list[str] = []
    code: list[str] = []
    fence_char = None
    fence_length = 0

    for line in _LINE_REGEX.findall(content):
        match = _FENCE_REGEX.match(line)
        if fence_char is None:
            if match:
                if text:
                    yield "".join(text), False
                    text = []
                fence_char = match.group(1)[0]
                fence_length = len(match.group(1))
                code.append(line)
            else:
                text.append(line)
        else:
            code.append(line)
            if (
                match
                and match.group(1)[0] == fence_char
                and len(match.group(1)) >= fence_length
                and _FENCE_CLOSE_TAIL_REGEX.fullmatch(line, match.end())
            ):
                yield "".join(code), True
                code = []
                fence_char = None

    if text:
        yield "".join(text), False
    if code:
        yield "".join(code), True


def _iter_inline_code_segments(content: str) -> Iterator[tuple[str, bool]]:
    """
    Splits ``content`` into inline code spans and the text around them. A run
    of ``n`` backticks opens a span that the next run of exactly ``n`` backticks
    closes (CommonMark 6.1). Runs are matched once each, so this is linear.
    """

    runs = [(m.start(), m.end()) for m in _BACKTICK_RUN_REGEX.finditer(content)]
    if not runs:
        yield content, False
        return

    by_length: dict[int, list[int]] = {}
    for index, (start, end) in enumerate(runs):
        by_length.setdefault(end - start, []).append(index)
    next_position: dict[int, int] = {}

    position = 0
    index = 0
    while index < len(runs):
        start, end = runs[index]
        length = end - start
        candidates = by_length[length]
        cursor = next_position.get(length, 0)
        while cursor < len(candidates) and candidates[cursor] <= index:
            cursor += 1
        next_position[length] = cursor
        if cursor < len(candidates):
            closing = candidates[cursor]
            next_position[length] = cursor + 1
            if start > position:
                yield content[position:start], False
            yield content[start : runs[closing][1]], True
            position = runs[closing][1]
            index = closing + 1
        else:
            index += 1

    if position < len(content):
        yield content[position:], False


def iter_code_segments(content: str) -> Iterator[tuple[str, bool]]:
    """
    Yields ``(segment, is_code)`` pairs covering ``content`` in order. Code is a
    fenced block or an inline span, where markdown image syntax is literal text
    and must not be rewritten or resolved.
    """

    for segment, is_code in _iter_fence_segments(content):
        if is_code:
            yield segment, True
        else:
            yield from _iter_inline_code_segments(segment)


def map_outside_code(content: str, transform: Callable[[str], str]) -> str:
    """
    Applies ``transform`` to every non-code segment of ``content`` and leaves
    code segments untouched.
    """

    return "".join(
        segment if is_code else transform(segment)
        for segment, is_code in iter_code_segments(content)
    )


def _text_segments(content: str) -> Iterator[str]:
    for segment, is_code in iter_code_segments(content):
        if not is_code:
            yield segment


def extract_user_file_names(content: Optional[str]) -> set[str]:
    """
    Extract UserFile names from markdown image syntax ``![alt][filename]``.

    :param content: Markdown text that may contain image references.
    :return: Set of UserFile name strings found in the content.
    """

    if not content:
        return set()

    return {
        match.group("name")
        for segment in _text_segments(content)
        for match in MARKDOWN_IMAGE_REGEX.finditer(segment)
    }


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

    return sum(
        1
        for segment in _text_segments(content)
        for _ in MARKDOWN_IMAGE_REGEX.finditer(segment)
    )


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

    # Cheap shortcut for the common case: no image syntax at all.
    if "![" not in content:
        return content

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

    return map_outside_code(
        content, lambda segment: MARKDOWN_IMAGE_REGEX.sub(_replace, segment)
    )


def strip_user_file_urls(content: Optional[str]) -> str:
    """
    Strip resolved URLs from ``![alt][name](url)`` patterns, returning
    the DB-storage format ``![alt][name]``.

    :param content: Markdown text that may contain resolved image URLs.
    :return: Content with URLs stripped from image references.
    """

    if not content:
        return content or ""

    return map_outside_code(
        content,
        lambda segment: MARKDOWN_IMAGE_WITH_URL_REGEX.sub(r"\g<ref>", segment),
    )


def escape_user_file_references(
    content: Optional[str], names: Optional[Container[str]] = None
) -> Optional[str]:
    """
    Escapes ``![alt][name]`` references so they are stored and shown as literal text.

    :param content: Markdown text that may contain image references.
    :param names: Only escape the references to these names; all when omitted.
    :return: The content with those references escaped, or an empty value as is.
    """

    if not content:
        return content

    def _escape(match: re.Match) -> str:
        if names is not None and match.group("name") not in names:
            return match.group(0)
        return "!\\" + match.group(0)[1:]

    return map_outside_code(
        content, lambda segment: MARKDOWN_IMAGE_REGEX.sub(_escape, segment)
    )


def replace_user_file_images_with_alt(content: Optional[str]) -> str:
    """
    Replace all user file image references — ``![alt][name]`` and
    ``![alt][name](url)`` — with their alt text, producing a plain text
    representation of the content.

    :param content: Markdown text that may contain image references.
    :return: Content with image references replaced by their alt text.
    """

    if not content:
        return content or ""

    def _alt(match):
        return _ESCAPED_BRACKET_REGEX.sub(r"\1", match.group("alt"))

    def _replace(segment):
        segment = MARKDOWN_IMAGE_WITH_URL_REGEX.sub(_alt, segment)
        return MARKDOWN_IMAGE_REGEX.sub(_alt, segment)

    return map_outside_code(content, _replace)


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

    return map_outside_code(
        content, lambda segment: MARKDOWN_IMAGE_REGEX.sub(_trim, segment)
    )


def is_renderable_user_file(user_file) -> bool:
    """
    Whether the given user file may be embedded as an image in a rich text cell.

    :param user_file: A ``UserFile`` instance.
    :return: True if the file is an image or an SVG.
    """

    return bool(user_file.is_image) or (
        (user_file.original_extension or "").lower() in RENDERABLE_NON_IMAGE_EXTENSIONS
    )
