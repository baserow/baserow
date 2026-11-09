from collections.abc import Iterable
from html.parser import HTMLParser

import html5lib

_URL_CONTROLS = "".join(chr(i) for i in range(33))
_URL_WHITESPACE = str.maketrans("", "", "\t\n\r")
_URL_ATTRIBUTES = {
    "href",
    "xlink:href",
    "src",
    "action",
    "formaction",
    "data",
    "codebase",
}
HTML_ERROR = (
    "Enter static HTML only. Add JavaScript in the application's Custom code settings."
)


def _is_static_tag(tag: str, attributes: Iterable[tuple[str, str | None]]) -> bool:
    if tag == "script":
        return False
    for key, value in attributes:
        name = key.rsplit("}", 1)[-1].lower()
        if name.startswith("on") or name == "srcdoc":
            return False
        if not value:
            continue
        if name in _URL_ATTRIBUTES:
            # Attribute entities are already decoded. URL parsing ignores ASCII
            # tabs and newlines anywhere and strips leading C0 controls and spaces.
            url = value.translate(_URL_WHITESPACE).lstrip(_URL_CONTROLS).lower()
            if url.startswith("javascript:"):
                return False
            if tag in {"iframe", "object", "embed"} and url.startswith("data:"):
                return False
        # SVG animations can change a link's destination after validation.
        if tag in {"set", "animate"} and name == "attributename":
            target = value.lower().split(":")[-1]
            if target in _URL_ATTRIBUTES or target.startswith("on"):
                return False
    return True


class _SourceTags(HTMLParser):
    """Check tags discarded during HTML5 tree construction and error recovery."""

    valid = True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if not _is_static_tag(tag, attrs):
            self.valid = False


def is_static_html(html: object) -> bool:
    if not isinstance(html, str):
        return False
    parser = html5lib.HTMLParser()
    fragment = parser.parseFragment(html, scripting=True)
    for node in fragment.iter():
        if isinstance(node.tag, str) and not _is_static_tag(
            node.tag.rsplit("}", 1)[-1].lower(), node.attrib.items()
        ):
            return False
    if parser.errors:
        source = _SourceTags()
        source.feed(html)
        source.close()
        return source.valid
    return True
