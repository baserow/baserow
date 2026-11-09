import re
from collections.abc import Iterator
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
    "poster",
    "cite",
    "background",
    "codebase",
}
_SRCSET_URL = re.compile(r"[,\t\n\f\r ]*([^\t\n\f\r ]+)")
_SRCSET_DESCRIPTORS = re.compile(r"(?:[^,(]|\([^)]*(?:\)|$))*(?:,|$)")
_REFRESH_PREFIX = re.compile(
    r"""^\s*[.\d]+[\s;,]+(?:url\s*=\s*)?['"]?""", re.I | re.ASCII
)
HTML_ERROR = (
    "Enter static HTML only. Add JavaScript in the application's Custom code settings. "
    "Use srcdoc or an external URL for embedded documents."
)


def _srcset_urls(value: str) -> Iterator[str]:
    # Commas can be part of a URL (e.g. a data image). Otherwise they end
    # a candidate after its descriptors, except inside parentheses.
    position = 0
    while match := _SRCSET_URL.match(value, position):
        url = match[1]
        yield url.rstrip(",")
        position = match.end()
        if not url.endswith(","):
            descriptors = _SRCSET_DESCRIPTORS.match(value, position)
            assert descriptors is not None
            position = descriptors.end()


def _urls(tag: str, attrs: dict[str, str]) -> Iterator[str]:
    for name, value in attrs.items():
        if name in _URL_ATTRIBUTES or (tag == "object" and name == "data"):
            yield value
        elif name in {"srcset", "imagesrcset"}:
            yield from _srcset_urls(value)
        elif name == "ping":
            yield from value.split()
    if tag == "meta" and attrs.get("http-equiv", "").lower() == "refresh":
        yield _REFRESH_PREFIX.sub("", attrs.get("content", ""), count=1)
    if tag in {"animate", "set"}:
        target = attrs.get("attributename", "").strip().lower().split(":")[-1]
        if target in _URL_ATTRIBUTES:
            yield from attrs.get("values", "").split(";")
            for name in ("from", "to", "by"):
                yield attrs.get(name, "")


class _StaticTags(HTMLParser):
    """Validate parsed elements, including source tags lost during HTML5 recovery."""

    def __init__(self, documents: set[str]):
        super().__init__()
        self.documents = documents
        self.valid = True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {
            key.replace("{http://www.w3.org/1999/xlink}", "xlink:").lower(): value or ""
            for key, value in attrs
        }
        if tag == "script" or any(key.startswith("on") for key in attributes):
            self.valid = False
        if tag == "iframe" and "srcdoc" in attributes:
            self.documents.add(attributes["srcdoc"])
        if tag in {"animate", "set"}:
            target = attributes.get("attributename", "").strip().lower().split(":")[-1]
            if target.startswith("on") or target in {"srcdoc", "attributename"}:
                self.valid = False
        for url in _urls(tag, attributes):
            normalized = url.translate(_URL_WHITESPACE).lstrip(_URL_CONTROLS).lower()
            if normalized.startswith("javascript:") or (
                tag in {"iframe", "object", "embed"} and normalized.startswith("data:")
            ):
                self.valid = False


def is_static_html(html: object) -> bool:
    if not isinstance(html, str):
        return False
    documents: set[str] = set()
    full_document = False
    while True:
        parser = html5lib.HTMLParser()
        parse = parser.parse if full_document else parser.parseFragment
        root = parse(html, scripting=True)
        tags = _StaticTags(documents)
        for node in root.iter():
            if isinstance(node.tag, str):
                tags.handle_starttag(
                    node.tag.rsplit("}", 1)[-1].lower(), list(node.attrib.items())
                )
        if parser.errors:
            tags.feed(html)
            tags.close()
        if not tags.valid:
            return False
        if not documents:
            return True
        html = documents.pop()
        full_document = True
