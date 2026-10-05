import html
import re

# Slack renders its own "mrkdwn" dialect, not Markdown: bold is *text*,
# italic _text_, headings do not exist, links are <url|label> and bullets are
# plain characters. The agent answers in Markdown, so its answers are
# translated before they are posted.

_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`\n]+`")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_ITALIC = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")
_STRIKE = re.compile(r"~~(.+?)~~")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_BULLET = re.compile(r"^(\s*)[-*+]\s+")
_RULE = re.compile(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$")
_PLACEHOLDER = "\x00{}\x00"


def markdown_to_mrkdwn(text: str) -> str:
    """
    Converts Markdown to Slack mrkdwn. Code blocks and inline code are kept
    verbatim; `&`, `<` and `>` in prose are escaped because Slack treats them
    as markup.
    """

    protected: list[str] = []

    def protect_text(value: str) -> str:
        protected.append(value)
        return _PLACEHOLDER.format(len(protected) - 1)

    def protect(match: re.Match) -> str:
        return protect_text(match.group(0))

    text = _CODE_FENCE.sub(protect, text)
    text = _INLINE_CODE.sub(protect, text)

    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = _LINK.sub(lambda m: f"<{m.group(2)}|{m.group(1)}>", text)

    lines = []
    for line in text.split("\n"):
        if _RULE.match(line):
            continue
        heading = _HEADING.match(line)
        if heading:
            lines.append(protect_text(f"*{heading.group(1)}*"))
            continue
        lines.append(_BULLET.sub(lambda m: f"{m.group(1)}• ", line))
    text = "\n".join(lines)

    # Converted bold is protected too, otherwise the italic pass would read
    # its single asterisks as Markdown italics.
    text = _BOLD.sub(lambda m: protect_text(f"*{m.group(1) or m.group(2)}*"), text)
    text = _ITALIC.sub(lambda m: f"_{m.group(1)}_", text)
    text = _STRIKE.sub(lambda m: f"~{m.group(1)}~", text)

    for index, original in enumerate(protected):
        text = text.replace(_PLACEHOLDER.format(index), original)
    return text


def slack_text_to_plain(text: str) -> str:
    """
    Turns the text of an inbound Slack message into plain text for the
    agent: Slack escapes `&`, `<` and `>` and wraps links as <url|label>.
    """

    text = re.sub(r"<(https?://[^|>]+)\|([^>]+)>", r"\2 (\1)", text)
    text = re.sub(r"<(https?://[^>]+)>", r"\1", text)
    return html.unescape(text)
