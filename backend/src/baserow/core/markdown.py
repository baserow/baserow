"""
Renders the markdown stored by rich text fields as clean HTML, for the
``markdown_to_html`` runtime formula function.

The frontend executes the same formulas in the browser and during SSR with
``web-frontend/modules/core/utils/markdownToHtml.js``. Both sides configure
markdown-it the same way and the rules below are ports of the JavaScript ones, so
the same markdown produces the same HTML.
"""

from functools import cache
from typing import Optional, Sequence

from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML
from markdown_it.rules_core import StateCore
from markdown_it.token import Token
from markdown_it.utils import EnvType, OptionsDict

from baserow.contrib.database.fields.rich_text_utils import (
    MARKDOWN_IMAGE_WITH_URL_REGEX,
    append_user_file_urls,
    map_outside_code,
)

_TASK_LIST_MARKERS = ("[ ] ", "[x] ", "[X] ")
_TASK_LIST_CHECKBOX = (
    '<input class="task-list-item-checkbox"{checked} disabled="" type="checkbox">'
)


def _task_lists(state: StateCore) -> None:
    """
    Port of the ``markdown-it-task-lists`` core rule with ``enabled: false`` and
    ``label: false``, which is how the frontend renderer configures the plugin.
    """

    tokens = state.tokens
    for index in range(2, len(tokens)):
        token = tokens[index]
        if not (
            token.type == "inline"
            and tokens[index - 1].type == "paragraph_open"
            and tokens[index - 2].type == "list_item_open"
            # markdown-it has already trimmed the leading whitespace of the item.
            and token.content.startswith(_TASK_LIST_MARKERS)
        ):
            continue

        checked = "" if token.content.startswith("[ ] ") else ' checked=""'
        checkbox = Token("html_inline", "", 0)
        checkbox.content = _TASK_LIST_CHECKBOX.format(checked=checked)
        token.children.insert(0, checkbox)
        token.children[1].content = token.children[1].content[3:]
        token.content = token.content[3:]

        list_item = tokens[index - 2]
        list_item.attrSet("class", "task-list-item")
        # The enclosing list is the closest previous token one level up.
        for parent in reversed(tokens[: index - 2]):
            if parent.level == list_item.level - 1:
                parent.attrSet("class", "contains-task-list")
                break


def _render_link_open(
    self: RendererHTML,
    tokens: Sequence[Token],
    idx: int,
    options: OptionsDict,
    env: EnvType,
) -> str:
    tokens[idx].attrSet("rel", "noopener noreferrer")
    return self.renderToken(tokens, idx, options, env)


@cache
def _get_parser() -> MarkdownIt:
    """
    The ``js-default`` preset is what ``new MarkdownIt({ html: false })`` gives
    the frontend: tables and strikethrough on, raw HTML escaped, no linkify, no
    typographer, soft line breaks kept. The parser is stateless once configured.
    """

    parser = MarkdownIt("js-default")
    parser.core.ruler.after("inline", "github_task_lists", _task_lists)
    parser.add_render_rule("link_open", _render_link_open)
    return parser


def _to_markdown_image(segment: str) -> str:
    return MARKDOWN_IMAGE_WITH_URL_REGEX.sub(r"![\g<alt>](\g<url>)", segment)


def _rewrite_image_references(content: str) -> str:
    """
    Turns Baserow image references outside code into standard markdown images so
    they render as ``<img>``. The API form ``![alt][name](url)`` keeps its URL; a
    bare ``![alt][name]`` (the storage form, e.g. a literal typed into a formula)
    is resolved to its current storage URL first.
    """

    content = map_outside_code(content, _to_markdown_image)
    if "![" in content:
        content = map_outside_code(append_user_file_urls(content), _to_markdown_image)
    return content


def markdown_to_html(content: Optional[str]) -> str:
    """
    Converts markdown, such as the value of a rich text field, to HTML.

    :param content: The markdown to render. Empty values render as ``""``.
    :return: The HTML without leading or trailing whitespace.
    """

    if not content:
        return ""

    return _get_parser().render(_rewrite_image_references(content)).strip()
