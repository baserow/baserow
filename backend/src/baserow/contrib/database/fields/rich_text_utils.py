import re
from typing import Callable, Iterator, Optional

from markdown_it import MarkdownIt

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
# Parentheses are excluded too: the extension is taken verbatim from the
# uploaded filename, and a ``)`` in it would terminate the ``(url)`` group early.
# The extension may be empty: a file uploaded without one is named ``unique_hash.``.
_NAME_PATTERN = r"[a-zA-Z0-9]+_[a-zA-Z0-9]+\.[^\]\s/\\()]*"

# ``![alt][name]`` — the storage format of a Baserow user file image.
MARKDOWN_IMAGE_REGEX = re.compile(
    rf"!\[(?P<alt>{_ALT_PATTERN})\]\[(?P<name>{_NAME_PATTERN})\]"
)

# ``![alt][name](url)`` — the API format with the resolved storage URL appended.
MARKDOWN_IMAGE_WITH_URL_REGEX = re.compile(
    rf"(?P<ref>!\[(?P<alt>{_ALT_PATTERN})\]\[(?P<name>{_NAME_PATTERN})\])"
    # The URL can't contain whitespace or parentheses, so a failed match stops at
    # the next ``(`` instead of rescanning the rest of the input (quadratic time
    # on ``'![x][a_b.png](' * n``). Storage URLs never contain either.
    r"\((?P<url>[^()\s]*)\)"
)

# ``![alt](url)`` — a plain markdown image (external URL, not a Baserow upload).
# Cannot match the Baserow forms above because there ``]`` is followed by
# ``[name]`` rather than ``(``. The destination allows one level of balanced
# parentheses like CommonMark does, and whitespace for a title, but no unbalanced
# ``(``, so a failed match is bounded by the next ``(`` and ``'![x](' * n`` stays
# linear.
MARKDOWN_PLAIN_IMAGE_REGEX = re.compile(
    rf"!\[(?P<alt>{_ALT_PATTERN})\]\((?P<url>(?:[^()]|\([^()]*\))*)\)"
)

_ESCAPED_BRACKET_REGEX = re.compile(r"\\([\[\]])")

_BACKTICK_RUN_REGEX = re.compile(r"`+")
# markdown-it splits lines on these after normalizing, so ``str.splitlines`` (which
# also splits on ``\v``, ``\x1c``, ``\u2028``...) would disagree on line numbers.
_LINE_REGEX = re.compile(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$")

# The parsers use the same preset as the frontend (``new Markdown({ html: false })``),
# so both sides agree on what is code and what is an image. HTML is disabled on
# both, so an ``<img>`` tag is never rendered.
# Block structure only: code blocks are block tokens, so the inline pass is skipped.
_BLOCK_MARKDOWN = MarkdownIt("js-default").disable("inline")
# Inline pass for image detection. The disabled rules only post-process emphasis
# and merge text tokens, never create images, and ``fragments_join`` is quadratic
# on long inputs.
_INLINE_MARKDOWN = MarkdownIt("js-default").disable(
    ["balance_pairs", "emphasis", "strikethrough", "fragments_join", "text_join"]
)
# The inline parse is linear, but each character that can start an inline rule
# costs a few µs and each ``[`` ~50µs (link label scan), so ``'![[[' * n`` of
# 100KB takes seconds. The paragraphs that need parsing get a budget of about
# half a second, and content over it is treated as containing an image.
MAX_INLINE_IMAGE_SCAN_COST = 200_000
_INLINE_BRACKET_COST = 20
# markdown-it's inline text rule consumes everything else in one step.
_INLINE_RULE_START_REGEX = re.compile(r"[\n!#$%&*+\-:<=>@\[\\\]^_`{}~]")


def _may_contain_code_block(content: str) -> bool:
    """
    Cheap pre-check: a code block needs a fence or four columns of indentation.
    """

    return "```" in content or "~~~" in content or "    " in content or "\t" in content


def _iter_block_segments(content: str) -> Iterator[tuple[str, bool]]:
    """
    Splits ``content`` into code blocks (fenced or indented, at any nesting level
    such as inside a list or blockquote) and the text around them, using the line
    ranges markdown-it reports for its ``code_block`` and ``fence`` tokens.
    """

    if not _may_contain_code_block(content):
        yield content, False
        return

    code_lines: list[tuple[int, int]] = [
        tuple(token.map)
        for token in _BLOCK_MARKDOWN.parse(content)
        if token.type in ("code_block", "fence") and token.map
    ]
    if not code_lines:
        yield content, False
        return

    lines = _LINE_REGEX.findall(content)
    is_code = [False] * len(lines)
    for start, end in code_lines:
        for line_number in range(start, min(end, len(lines))):
            is_code[line_number] = True

    buffer: list[str] = []
    current = is_code[0] if lines else False
    for line, line_is_code in zip(lines, is_code):
        if line_is_code != current and buffer:
            yield "".join(buffer), current
            buffer = []
        current = line_is_code
        buffer.append(line)
    if buffer:
        yield "".join(buffer), current


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
    fenced or indented block or an inline span, where markdown image syntax is
    literal text and must not be rewritten or resolved.
    """

    for segment, is_code in _iter_block_segments(content):
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


def demote_external_images_to_links(content: Optional[str]) -> str:
    """
    Rewrite every plain markdown image ``![alt](url)`` into a link ``[alt](url)``.

    Rich text images are Baserow user files only. A form can be submitted
    anonymously and the resulting row can be shown in a public view, so an
    external image would be fetched by every reader from a host the workspace
    does not control: that leaks reader IPs and lets the remote content be
    swapped after anyone reviewed it. Degrading to a link keeps the URL visible
    without the page loading it.

    Mirrors ``demoteExternalImagesToLinks`` on the frontend.

    :param content: Markdown text that may contain plain image syntax.
    :return: Content with plain images converted to links.
    """

    if not content:
        return content or ""

    def _demote(match):
        return f"[{match.group('alt')}]({match.group('url')})"

    return map_outside_code(
        content, lambda segment: MARKDOWN_PLAIN_IMAGE_REGEX.sub(_demote, segment)
    )


def normalize_rich_text_for_storage(content: Optional[str]) -> str:
    """
    Brings any accepted rich text input into the stored form: resolved URLs are
    stripped from user file references and external images are demoted to links.
    Every write path (API, import, data sync, handler callers) must go through
    this so the stored value has a single shape.

    :param content: Markdown text as received.
    :return: The content in the storage format.
    """

    if not content:
        return content or ""

    return demote_external_images_to_links(strip_user_file_urls(content))


def _iter_image_tokens(tokens) -> Iterator:
    for token in tokens:
        if token.type == "image":
            yield token
        if token.children:
            yield from _iter_image_tokens(token.children)


def _has_foreign_image_opener(content: str) -> bool:
    """
    Whether ``content`` has a ``![`` that isn't the stored ``![alt][name]`` form.
    Escaped openers count too: a backslash inside a code span is literal.
    """

    return any(
        not _OUR_IMAGE_AHEAD_REGEX.match(content, match.end())
        for match in _IMAGE_OPENER_REGEX.finditer(content)
    )


def contains_markdown_image(content: Optional[str]) -> bool:
    """
    Whether a markdown renderer would draw any image for ``content``.

    The stored format ``![alt][name]`` is a reference with no matching definition,
    so it renders as text and the frontend swaps it for the user file. Anything
    markdown-it itself turns into an image, such as ``![x][ref]`` with a
    ``[ref]: https://...`` definition, a nested alt label, or a definition that
    shadows a user file name, would load a URL the workspace doesn't control.

    Only paragraphs that could hold such an image are parsed inline: ones with a
    foreign ``![``, or any ``![`` when a definition label looks like a user file
    name. If those exceed ``MAX_INLINE_IMAGE_SCAN_COST`` the answer is True.

    :param content: Markdown text, already normalized for storage.
    :return: True if markdown-it produces at least one image token.
    """

    if not content or "![" not in content:
        return False

    env: dict = {}
    tokens = _BLOCK_MARKDOWN.parse(content, env)
    shadows_file_name = any(
        _NAME_LABEL_REGEX.fullmatch(label) for label in env.get("references", {})
    )
    to_scan = [
        token.content
        for token in tokens
        if token.type == "inline"
        and "![" in token.content
        and (shadows_file_name or _has_foreign_image_opener(token.content))
    ]
    cost = sum(
        len(_INLINE_RULE_START_REGEX.findall(text))
        + _INLINE_BRACKET_COST * text.count("[")
        for text in to_scan
    )
    if cost > MAX_INLINE_IMAGE_SCAN_COST:
        return True

    return any(
        next(_iter_image_tokens(_INLINE_MARKDOWN.parseInline(text, env)), None)
        is not None
        for text in to_scan
    )


# A reference definition whose label could match a user file name. Labels match
# case-insensitively and ignore surrounding whitespace, and a definition can sit
# inside a blockquote or a list item.
_FILE_NAME_DEFINITION_REGEX = re.compile(
    # Whitespace only ever leads a marker, so the prefix has a single parse and
    # can't backtrack exponentially on ``'> ' * n``.
    rf"^(?P<prefix>(?:[ \t]*(?:>|[-+*]|\d{{1,9}}[.)]))*[ \t]*)"
    rf"\[(?=[ \t]*{_NAME_PATTERN}[ \t]*\]:)",
    re.MULTILINE | re.IGNORECASE,
)
_OUR_IMAGE_AHEAD = rf"(?={_ALT_PATTERN}\]\[{_NAME_PATTERN}\])"
_OUR_IMAGE_AHEAD_REGEX = re.compile(_OUR_IMAGE_AHEAD)
_IMAGE_OPENER_REGEX = re.compile(r"!\[")
# markdown-it normalizes reference labels (collapsed whitespace, case folded).
_NAME_LABEL_REGEX = re.compile(_NAME_PATTERN, re.IGNORECASE)


def _escape_image_openers(content: str, keep_ours: bool) -> str:
    """
    Escapes every unescaped ``![`` so it renders as ``!`` followed by a link.

    :param keep_ours: Leave the stored ``![alt][name]`` form alone.
    """

    parts = []
    position = 0
    for match in _IMAGE_OPENER_REGEX.finditer(content):
        start = match.start()
        backslashes = 0
        while start - backslashes > 0 and content[start - backslashes - 1] == "\\":
            backslashes += 1
        if backslashes % 2 == 1:
            continue
        if keep_ours and _OUR_IMAGE_AHEAD_REGEX.match(content, match.end()):
            continue
        parts.append(content[position:start])
        parts.append("\\")
        position = start
    parts.append(content[position:])
    return "".join(parts)


def neutralize_markdown_images(content: Optional[str]) -> str:
    """
    Makes sure markdown-it renders no image for ``content``, while keeping the
    stored ``![alt][name]`` user file references.

    Used on paths that can't reject a value, such as import and data sync, where
    the API would answer 400 instead. Every foreign image opener is escaped and
    reference definitions that could shadow a user file name are escaped. If an
    image survives that, every image opener is escaped, the user file references
    included, and as a last resort code is escaped too.

    :param content: Markdown text, already normalized for storage.
    :return: Content for which ``contains_markdown_image`` is False.
    """

    if not contains_markdown_image(content):
        return content or ""

    content = map_outside_code(
        content, lambda segment: _escape_image_openers(segment, keep_ours=True)
    )
    content = map_outside_code(
        content,
        lambda segment: _FILE_NAME_DEFINITION_REGEX.sub(r"\g<prefix>\\[", segment),
    )
    if not contains_markdown_image(content):
        return content

    content = map_outside_code(
        content, lambda segment: _escape_image_openers(segment, keep_ours=False)
    )
    if not contains_markdown_image(content):
        return content

    return _escape_image_openers(content, keep_ours=False)


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

    def _replace(segment):
        segment = MARKDOWN_IMAGE_WITH_URL_REGEX.sub(_alt, segment)
        segment = MARKDOWN_IMAGE_REGEX.sub(_alt, segment)
        return MARKDOWN_PLAIN_IMAGE_REGEX.sub(_alt, segment)

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
