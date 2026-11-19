import codecs
import json
import re
import time
from typing import Any

import requests
from asgiref.sync import sync_to_async
from bs4.dammit import EncodingDetector
from loguru import logger
from pydantic_ai import RunContext, Tool
from pydantic_ai.common_tools.web_fetch import _convert_html
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ModelResponse, ToolCallPart
from requests import exceptions as request_exceptions

from advocate.connection import UnacceptableAddressException
from baserow.contrib.integrations.utils import send_http_request
from baserow.core.services.exceptions import (
    RedirectNotAllowedDispatchException,
    ResponseTooLargeDispatchException,
)
from baserow.core.tools.errors import ToolError, ToolErrorCode
from baserow.version import VERSION as BASEROW_VERSION

from .constants import (
    WEB_FETCH_MAX_CHARACTERS,
    WEB_FETCH_MAX_CONVERTED_CHARACTERS,
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
# The converter drops these tags but keeps their text, which on most pages is
# mostly script. A tag cut off by the size limit runs to the end.
NON_TEXT_TAGS = re.compile(
    r"<(script|style|noscript|template|svg)\b[^>]*>.*?(?:</\1\s*>|\Z)",
    re.IGNORECASE | re.DOTALL,
)
MEDIA_TYPE = re.compile(
    r"[a-z0-9][a-z0-9!#$&^_.+-]{0,63}/[a-z0-9][a-z0-9!#$&^_.+-]{0,63}"
)
# How files start, for those sent without their type or as text.
FILE_SIGNATURES = (
    b"%PDF",
    b"\x89PNG",
    b"GIF8",
    b"\xff\xd8\xff",
    b"PK\x03\x04",
    b"\x1f\x8b",
    b"RIFF",
    b"OggS",
    b"ID3",
    b"7z\xbc\xaf",
    b"Rar!",
)
UTF16_BOMS = (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)
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
        the run's messages so parallel calls and resumed runs count too. Only the
        response that made this call is searched for its id, since providers may
        reuse an id in a later response.
    """

    responses = [
        [
            part.tool_call_id
            for part in message.parts
            if isinstance(part, ToolCallPart) and part.tool_name == WEB_FETCH_TOOL_NAME
        ]
        for message in ctx.messages
        if isinstance(message, ModelResponse)
    ]
    if not responses:
        return 0
    *earlier, current = responses
    before = sum(len(calls) for calls in earlier)
    try:
        return before + current.index(ctx.tool_call_id)
    except ValueError:
        return before + len(current)


def _download(url: str):
    """
    Download the page through the same outbound HTTP stack as the HTTP request
    integration: its address checks on every redirect, its body size ceiling and
    one deadline for the whole exchange. Internal addresses are always refused.

    :param url: The page.
    :return: The response, its body read.
    """

    return send_http_request(
        "GET",
        url,
        deadline=time.monotonic() + WEB_FETCH_TIMEOUT,
        operation_timeout=WEB_FETCH_TIMEOUT,
        # The model picks the URL and a page can steer it, so the setting that
        # lets integrations reach internal services doesn't apply here.
        refuse_private_addresses=True,
        send_netrc_credentials=False,
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
    :raises Exception: Whatever the converter raises for a page it can't convert.
    """

    if media_type in MARKDOWN_MEDIA_TYPES:
        return "", text
    if not media_type or media_type in HTML_MEDIA_TYPES:
        # The SDK's converter bounds the work a crafted page can cause. It's
        # private, so an upgrade of the pinned SDK may rename it.
        return _convert_html(NON_TEXT_TAGS.sub("", text))
    if media_type == "application/json":
        try:
            return "", f"```json\n{json.dumps(json.loads(text), indent=2)}\n```"
        except (ValueError, RecursionError):
            return "", text
    return "", text


def _media_type(response: requests.Response) -> str:
    """
    :param response: The page.
    :return: Its media type, empty when the server sent none or a malformed one.
    """

    media_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    return media_type if MEDIA_TYPE.fullmatch(media_type) else ""


def _charset(response: requests.Response, html: bool) -> str:
    """
    :param response: The page.
    :param html: Whether the page is HTML, which can declare its charset itself.
    :return: The charset the header names, else the one an HTML page declares,
        else UTF-8. Requests assumes ISO-8859-1 for text without a header charset.
    """

    for param in response.headers.get("content-type", "").split(";")[1:]:
        name, _, value = param.partition("=")
        if name.strip().lower() == "charset" and value.strip(" \"'"):
            return value.strip(" \"'")
    if html:
        declared = EncodingDetector.find_declared_encoding(
            response.content, is_html=True
        )
        if declared:
            return declared
    return "utf-8"


def _decode(response: requests.Response, html: bool) -> str:
    charset = _charset(response, html)
    try:
        return response.content.decode(charset, errors="replace")
    except LookupError:
        return response.content.decode("utf-8", errors="replace")


def _is_file(content: bytes) -> bool:
    """
    :param content: The page's body.
    :return: Whether it starts like a file, whatever type the server named.
    """

    start = content[:1024]
    return start.startswith(FILE_SIGNATURES) or (
        b"\x00" in start and not start.startswith(UTF16_BOMS)
    )


def _is_text(media_type: str) -> bool:
    if media_type.startswith("image/"):
        return False
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
    media_type = _media_type(response)
    if not _is_text(media_type):
        return _failed(
            f"The page is a file ({media_type}), not text, so it can't be opened."
        )
    if _is_file(response.content):
        return _failed("The page is a file, not text, so it can't be opened.")
    html = not media_type or media_type in HTML_MEDIA_TYPES
    # Converting happens after the download's deadline, so the text it gets is
    # bounded too.
    text = _decode(response, html)[:WEB_FETCH_MAX_CONVERTED_CHARACTERS]
    try:
        title, content = _to_text(media_type, text)
    except (ModelRetry, RecursionError, ValueError):
        return _failed("The page is too complex to read.")
    except Exception as exc:
        logger.error("Agent web fetch couldn't convert a page ({})", type(exc).__name__)
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
