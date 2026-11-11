import pytest

from baserow.contrib.database.fields.rich_text_utils import resolve_user_file_urls
from baserow.core.markdown import markdown_to_html

# Keep these vectors identical to the ones in
# web-frontend/test/unit/core/utils/markdownToHtml.spec.js: both renderers must
# produce the same HTML for the same markdown.
SHARED_VECTORS = [
    ("", ""),
    ("**bold** _italic_", "<p><strong>bold</strong> <em>italic</em></p>"),
    ("# Title\n\ntext", "<h1>Title</h1>\n<p>text</p>"),
    # Raw HTML is escaped.
    ("<b>x</b>", "<p>&lt;b&gt;x&lt;/b&gt;</p>"),
    # markdown-it refuses unsafe link destinations and renders them literally.
    ("[a](javascript:alert(1))", "<p>[a](javascript:alert(1))</p>"),
    (
        "[ok](https://e.com)",
        '<p><a href="https://e.com" rel="noopener noreferrer">ok</a></p>',
    ),
    ("~~s~~", "<p><s>s</s></p>"),
    # Non-standard editor marks stay literal, like in the grid preview.
    ("++u++ ~sub~", "<p>++u++ ~sub~</p>"),
    (
        "| a |\n|---|\n| b |",
        "<table>\n<thead>\n<tr>\n<th>a</th>\n</tr>\n</thead>\n"
        "<tbody>\n<tr>\n<td>b</td>\n</tr>\n</tbody>\n</table>",
    ),
    # Soft line breaks are kept as is.
    ("line1\nline2", "<p>line1\nline2</p>"),
    (
        "- [ ] open\n- [x] done",
        '<ul class="contains-task-list">\n'
        '<li class="task-list-item"><input class="task-list-item-checkbox" '
        'disabled="" type="checkbox"> open</li>\n'
        '<li class="task-list-item"><input class="task-list-item-checkbox" '
        'checked="" disabled="" type="checkbox"> done</li>\n'
        "</ul>",
    ),
    # A Baserow image reference in its API form keeps the resolved URL.
    (
        "![logo][abc_def.png](https://cdn/x.png)",
        '<p><img src="https://cdn/x.png" alt="logo"></p>',
    ),
    (
        "![ext](https://other/x.png)",
        '<p><img src="https://other/x.png" alt="ext"></p>',
    ),
    # Image references inside code are left untouched.
    (
        "`![logo][abc_def.png](https://cdn/x.png)`",
        "<p><code>![logo][abc_def.png](https://cdn/x.png)</code></p>",
    ),
    # Mentions are plain text: the stored form cannot be told apart from an
    # email address or a time, so they are never resolved to names.
    ("@42 hi", "<p>@42 hi</p>"),
    ("john@42.com and meet @9", "<p>john@42.com and meet @9</p>"),
]


@pytest.mark.parametrize("content,expected", SHARED_VECTORS)
def test_markdown_to_html_shared_vectors(content, expected):
    assert markdown_to_html(content) == expected


def test_markdown_to_html_returns_empty_string_for_none():
    assert markdown_to_html(None) == ""


def test_markdown_to_html_resolves_bare_image_references_to_storage_urls():
    url = resolve_user_file_urls({"abc_def.png"})["abc_def.png"]

    result = markdown_to_html("![logo][abc_def.png] and `![x][abc_def.png]`")

    assert result == (
        f'<p><img src="{url}" alt="logo"> and <code>![x][abc_def.png]</code></p>'
    )
