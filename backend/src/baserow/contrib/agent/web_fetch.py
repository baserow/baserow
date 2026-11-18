import json
import time
from typing import Any

from asgiref.sync import sync_to_async
from loguru import logger
from pydantic_ai import RunContext, Tool
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ModelResponse, ToolCallPart
from requests import exceptions as request_exceptions

from baserow.core.tools.errors import ToolError, ToolErrorCode
from baserow.version import VERSION as BASEROW_VERSION

from .constants import (
    WEB_FETCH_MAX_CHARACTERS,
    WEB_FETCH_MAX_PER_REPLY,
    WEB_FETCH_TIMEOUT,
    WEB_FETCH_TOOL_NAME,
    WEB_SEARCH_STEP_QUERY_MAX_LENGTH,
)

WEB_FETCH_DESCRIPTION = (
    "Opens a web page by its http or https URL and returns its text as markdown. "
    "Only text pages can be opened, not files such as PDFs or images."
)
# Media types that are text even though they don't start with `text/`.
TEXT_MEDIA_TYPES = {
    "application/json",
    "application/ld+json",
    "application/xml",
    "application/xhtml+xml",
    "application/rss+xml",
    "application/atom+xml",
    "application/javascript",
}
HTML_MEDIA_TYPES = {"text/html", "application/xhtml+xml"}
MARKDOWN_MEDIA_TYPES = {"text/markdown", "text/x-markdown"}
NON_TEXT_TAGS = ["script", "style", "noscript", "template", "svg"]
TITLE_MAX_CHARACTERS = 200


def _failed(message: str) -> dict:
    """
    A failed fetch, returned rather than raised so the model reads why and the
    reply goes on: a raised retry counts against the tool's retry limit, and a
    few broken links in a row would end the whole reply.

    :param message: What went wrong, for the user and the model.
    :return: The tool result.
    """

    return {"error": ToolError(ToolErrorCode.FAILED, message).to_dict()}


def _fetch_index(ctx: RunContext[None]) -> int:
    """
    :param ctx: The run so far, with the response that made this call.
    :return: How many fetches the reply asked for before this one, counted from
        the run's messages so parallel calls and resumed runs count too.
    """

    calls = [
        part.tool_call_id
        for message in ctx.messages
        if isinstance(message, ModelResponse)
        for part in message.parts
        if isinstance(part, ToolCallPart) and part.tool_name == WEB_FETCH_TOOL_NAME
    ]
    try:
        return calls.index(ctx.tool_call_id)
    except ValueError:
        return len(calls)


def _download(url: str):
    """
    Download the page through the same outbound HTTP stack as the HTTP request
    integration: its address checks on every redirect, its body size ceiling and
    one deadline for the whole exchange.

    :param url: The page.
    :return: The response, its body read.
    """

    from baserow.contrib.integrations.utils import send_http_request

    return send_http_request(
        "GET",
        url,
        deadline=time.monotonic() + WEB_FETCH_TIMEOUT,
        operation_timeout=WEB_FETCH_TIMEOUT,
        headers={
            "user-agent": f"Baserow/{BASEROW_VERSION}/AgentWebFetch",
            "accept": "text/markdown, text/html;q=0.9, text/*;q=0.8",
        },
    )


def _to_text(media_type: str, text: str) -> tuple[str, str]:
    """
    :param media_type: The page's media type.
    :param text: The decoded body.
    :return: The page's title, empty when it has none, and its content as text.
    :raises ModelRetry: When the HTML is too costly to convert.
    :raises RecursionError: When the HTML is nested too deeply to convert.
    """

    if media_type in MARKDOWN_MEDIA_TYPES:
        return "", text
    if not media_type or media_type in HTML_MEDIA_TYPES:
        # Imported here: it needs the optional `markdownify` package, which only
        # replies that open pages should depend on. Its converter bounds the work a
        # crafted page can cause.
        from bs4 import BeautifulSoup
        from pydantic_ai.common_tools.web_fetch import _convert_html

        # The converter drops these tags but keeps their text, which on most
        # pages is mostly script.
        soup = BeautifulSoup(text, "html.parser")
        for tag in soup.find_all(NON_TEXT_TAGS):
            tag.decompose()
        return _convert_html(str(soup))
    if media_type == "application/json":
        try:
            return "", f"```json\n{json.dumps(json.loads(text), indent=2)}\n```"
        except (ValueError, RecursionError):
            return "", text
    return "", text


def _is_text(media_type: str) -> bool:
    return (
        not media_type
        or media_type.startswith("text/")
        or media_type in TEXT_MEDIA_TYPES
        or media_type.endswith("+json")
        or media_type.endswith("+xml")
    )


def _read_page(url: str) -> dict:
    """
    Fetch a page and turn it into text the model can read.

    :param url: The page.
    :return: The page's url, title and content, or the error.
    """

    from advocate.connection import UnacceptableAddressException
    from baserow.core.services.exceptions import (
        RedirectNotAllowedDispatchException,
        ResponseTooLargeDispatchException,
    )

    try:
        response = _download(url)
    except ResponseTooLargeDispatchException:
        return _failed("The page is too large to open.")
    except request_exceptions.Timeout:
        return _failed("The page took too long to answer.")
    except request_exceptions.TooManyRedirects:
        return _failed("The page redirected too many times.")
    except (
        UnacceptableAddressException,
        RedirectNotAllowedDispatchException,
        request_exceptions.RequestException,
        ValueError,
    ):
        # One message for internal addresses, unknown hosts and refused
        # connections, so the model can't use the error to map the network.
        return _failed("The page couldn't be opened.")
    except Exception as exc:
        logger.error("Agent web fetch failed ({})", type(exc).__name__)
        return _failed("The page couldn't be opened.")

    if response.status_code >= 400:
        return _failed(f"The page answered with status {response.status_code}.")
    media_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if not _is_text(media_type):
        return _failed(
            f"The page is a file ({media_type}), not text, so it can't be opened."
        )
    try:
        text = response.content.decode(response.encoding or "utf-8", errors="replace")
        title, content = _to_text(media_type, text)
    except (UnicodeError, LookupError):
        return _failed("The page's text couldn't be read.")
    except (ModelRetry, RecursionError):
        return _failed("The page is too complex to read.")
    content = content.strip()
    if len(content) > WEB_FETCH_MAX_CHARACTERS:
        content = content[:WEB_FETCH_MAX_CHARACTERS] + "\n\n[Content truncated]"
    title = " ".join(title.split())[:TITLE_MAX_CHARACTERS]
    return {"url": url, "title": title, "content": content}


async def web_fetch(ctx: RunContext[None], url: str) -> dict[str, Any]:
    """
    Opens a web page by its URL and returns its text.

    :param url: The http or https URL of the page.
    """

    if _fetch_index(ctx) >= WEB_FETCH_MAX_PER_REPLY:
        return _failed(
            f"This reply already opened {WEB_FETCH_MAX_PER_REPLY} pages, the most "
            "one reply may open."
        )
    url = url.strip()
    # The step records the URL as the only trace of what left the workspace, so a
    # URL it can't record in full isn't opened.
    if (
        not url.lower().startswith(("http://", "https://"))
        or len(url) > WEB_SEARCH_STEP_QUERY_MAX_LENGTH
        or any(char.isspace() or ord(char) < 32 for char in url)
    ):
        return _failed(
            "Only http and https URLs without spaces, of at most "
            f"{WEB_SEARCH_STEP_QUERY_MAX_LENGTH} characters, can be opened."
        )
    return await sync_to_async(_read_page, thread_sensitive=False)(url)


def web_fetch_tool() -> Tool[None]:
    """
    :return: The tool that opens web pages, which Baserow downloads itself so it
        works with every model.
    """

    return Tool(
        web_fetch,
        name=WEB_FETCH_TOOL_NAME,
        description=WEB_FETCH_DESCRIPTION,
        takes_ctx=True,
    )
