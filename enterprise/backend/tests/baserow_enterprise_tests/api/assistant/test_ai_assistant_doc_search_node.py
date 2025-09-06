import pytest
from enterprise.backend.src.baserow_enterprise.assistant.nodes.doc_search.handler import (
    _parse_toc_category,
)


def test_extracts_single_markdown_link():
    content = "Check out [Baserow](https://baserow.io) for more info."
    result = _parse_toc_category(content)
    assert result == [("Baserow", "https://baserow.io")]


def test_extracts_multiple_markdown_links():
    content = """
    Here are some links:
    [Documentation](https://docs.baserow.io)
    [GitHub](https://github.com/baserow/baserow)
    [Community](https://community.baserow.io)
    """
    result = _parse_toc_category(content)
    assert result == [
        ("Documentation", "https://docs.baserow.io"),
        ("GitHub", "https://github.com/baserow/baserow"),
        ("Community", "https://community.baserow.io"),
    ]


def test_extracts_relative_links():
    content = "See the [user guide](/docs/user-guide) and [API docs](../api/reference)."
    result = _parse_toc_category(content)
    assert result == [
        ("user guide", "/docs/user-guide"),
        ("API docs", "../api/reference"),
    ]


def test_extracts_links_with_different_protocols():
    content = """
    [Email](mailto:support@baserow.io)
    [FTP Server](ftp://files.example.com)
    [File](file:///home/user/document.pdf)
    """
    result = _parse_toc_category(content)
    assert result == [
        ("Email", "mailto:support@baserow.io"),
        ("FTP Server", "ftp://files.example.com"),
        ("File", "file:///home/user/document.pdf"),
    ]


def test_handles_links_with_special_characters():
    content = "[Query String](https://example.com/search?q=baserow&type=all#results)"
    result = _parse_toc_category(content)
    assert result == [
        ("Query String", "https://example.com/search?q=baserow&type=all#results")
    ]


def test_handles_links_with_spaces_in_text():
    content = "[This is a long link text](https://example.com)"
    result = _parse_toc_category(content)
    assert result == [("This is a long link text", "https://example.com")]


def test_returns_empty_list_for_no_links():
    content = "This is plain text without any markdown links."
    result = _parse_toc_category(content)
    assert result == []


def test_ignores_invalid_markdown_syntax():
    content = """
    [Incomplete link without URL]
    [Valid Link](https://valid.com)
    (https://url-without-text)
    """
    result = _parse_toc_category(content)
    assert result == [("Valid Link", "https://valid.com")]


def test_handles_nested_brackets_in_link_text():
    content = "[Link [with] brackets](https://example.com)"
    result = _parse_toc_category(content)
    # This will capture up to the first closing bracket
    assert result == [("Link [with", "https://example.com")]


def test_handles_empty_string():
    content = ""
    result = _parse_toc_category(content)
    assert result == []


def test_handles_links_on_same_line():
    content = "Check [link1](url1) and [link2](url2) on the same line"
    result = _parse_toc_category(content)
    assert result == [("link1", "url1"), ("link2", "url2")]
