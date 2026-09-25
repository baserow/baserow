import time
from types import SimpleNamespace

import pytest

from baserow.contrib.database.fields.rich_text_utils import (
    append_user_file_urls,
    count_image_references,
    escape_user_file_references,
    extract_user_file_names,
    is_renderable_user_file,
    iter_code_segments,
    keep_first_image_references,
    replace_user_file_images_with_alt,
    resolve_user_file_urls,
    strip_user_file_urls,
)

NAME = (
    "R7SiH9lsCNSxDKLRsabcjoqpu3YmYdmP_"
    "31f3aa68afe0ddc9027c18de4030fdb7df1434c10401ca23aab07d6fc308661c.png"
)


class TestExtractUserFileNames:
    def test_returns_empty_set_for_none(self):
        assert extract_user_file_names(None) == set()

    def test_returns_empty_set_for_empty_string(self):
        assert extract_user_file_names("") == set()

    def test_returns_empty_set_for_text_only(self):
        assert extract_user_file_names("Hello world, **bold** text") == set()

    def test_extracts_single_image(self):
        content = "Some text ![alt][abc123_def456.png] more text"
        assert extract_user_file_names(content) == {"abc123_def456.png"}

    def test_extracts_multiple_images(self):
        content = "![first][aaa111_bbb222.jpg]\ntext\n![second][ccc333_ddd444.webp]"
        assert extract_user_file_names(content) == {
            "aaa111_bbb222.jpg",
            "ccc333_ddd444.webp",
        }

    def test_deduplicates_same_image(self):
        content = "![a][abc_def.png] and ![b][abc_def.png]"
        assert extract_user_file_names(content) == {"abc_def.png"}

    def test_ignores_regular_links(self):
        content = "[click here](abc123_def456.png)"
        assert extract_user_file_names(content) == set()

    def test_ignores_standard_markdown_images(self):
        content = "![alt](https://example.com/image.png)"
        assert extract_user_file_names(content) == set()

    def test_ignores_non_userfile_names(self):
        content = "![alt][not-a-userfile.png]"
        assert extract_user_file_names(content) == set()

    def test_ignores_names_containing_parentheses(self):
        # A ``)`` in the extension would end the appended ``(url)`` early and
        # corrupt the value on every save, so such names are never a reference.
        content = "![alt][abc123_def456.png)] ![alt][abc123_def456.p(ng]"
        assert extract_user_file_names(content) == set()

    def test_handles_mixed_content(self):
        content = (
            "# Title\n"
            "Some text with [link](https://example.com)\n"
            "![image][abc123_def456.png]\n"
            "More **bold** text\n"
            "- list item\n"
        )
        assert extract_user_file_names(content) == {"abc123_def456.png"}

    def test_extracts_from_content_with_urls(self):
        content = "![img][abc123_def456.png](https://example.com/file.png)"
        assert extract_user_file_names(content) == {"abc123_def456.png"}


class TestResolveUserFileUrls:
    def test_returns_empty_dict_for_empty_set(self):
        assert resolve_user_file_urls(set()) == {}

    def test_resolves_name_to_url_string(self):
        result = resolve_user_file_urls({"abc123_def456.png"})

        assert "abc123_def456.png" in result
        url = result["abc123_def456.png"]
        assert isinstance(url, str)
        assert "user_files/" in url

    def test_resolves_any_name_without_db(self):
        result = resolve_user_file_urls({"nonexist_abcdef1234.png"})
        assert "nonexist_abcdef1234.png" in result
        assert "user_files/" in result["nonexist_abcdef1234.png"]

    def test_resolves_multiple_names(self):
        result = resolve_user_file_urls({"aaa_bbb.png", "ccc_ddd.jpg"})
        assert len(result) == 2
        assert "aaa_bbb.png" in result
        assert "ccc_ddd.jpg" in result


class TestAppendUserFileUrls:
    def test_returns_empty_string_for_none(self):
        assert append_user_file_urls(None) == ""

    def test_returns_content_unchanged_without_images(self):
        assert append_user_file_urls("Hello world") == "Hello world"

    def test_appends_url_to_image_reference(self):
        content = "![photo][abc123_def456.png]"
        result = append_user_file_urls(content)
        assert result.startswith("![photo][abc123_def456.png](")
        assert "user_files/" in result
        assert result.endswith(")")

    def test_re_resolves_existing_urls(self):
        content = "![photo][abc123_def456.png](https://old.example.com/old.png)"
        result = append_user_file_urls(content)
        assert "old.example.com" not in result
        assert "user_files/" in result

    def test_preserves_surrounding_text(self):
        content = "Before ![img][abc_def.png] After"
        result = append_user_file_urls(content)
        assert result.startswith("Before ")
        assert " After" in result


class TestStripUserFileUrls:
    def test_returns_empty_string_for_none(self):
        assert strip_user_file_urls(None) == ""

    def test_returns_content_unchanged_without_images(self):
        assert strip_user_file_urls("Hello") == "Hello"

    def test_strips_url_from_image_reference(self):
        content = "![photo][abc123_def456.png](https://example.com/file.png)"
        assert strip_user_file_urls(content) == "![photo][abc123_def456.png]"

    def test_strips_multiple_urls(self):
        content = (
            "![a][f1_h1.png](https://example.com/1.png) "
            "![b][f2_h2.jpg](https://example.com/2.jpg)"
        )
        assert strip_user_file_urls(content) == "![a][f1_h1.png] ![b][f2_h2.jpg]"


class TestRegexEdgeCases:
    def test_extracts_from_escaped_bracket_in_alt(self):
        content = r"![my\]pic][abc123_def456.png]"
        assert extract_user_file_names(content) == {"abc123_def456.png"}

    def test_strips_url_with_escaped_bracket_in_alt(self):
        content = r"![my\]pic][abc123_def456.png](https://example.com/f.png)"
        assert strip_user_file_urls(content) == r"![my\]pic][abc123_def456.png]"

    def test_appends_url_with_escaped_bracket_in_alt(self):
        content = r"![my\]pic][abc123_def456.png]"
        result = append_user_file_urls(content)
        assert result.startswith(r"![my\]pic][abc123_def456.png](")
        assert "user_files/" in result


class TestRegexHardening:
    def test_rejects_path_separators_in_name(self):
        content = "![x][abc_def.png/../../etc/passwd]"
        assert extract_user_file_names(content) == set()

    def test_rejects_backslash_in_name(self):
        content = r"![x][abc_def.png\..\secret]"
        assert extract_user_file_names(content) == set()

    def test_accepts_name_without_extension(self):
        content = "![x][abc_def.](http://h/abc_def.)"
        assert extract_user_file_names(content) == {"abc_def."}
        assert strip_user_file_urls(content) == "![x][abc_def.]"
        assert append_user_file_urls("![x][abc_def.]").startswith("![x][abc_def.](")

    def test_accepts_extension_with_query_string_or_dash(self):
        content = "![x][abc_def.jpeg?w=50] ![y][abc_def.jpg-resized]"
        assert extract_user_file_names(content) == {
            "abc_def.jpeg?w=50",
            "abc_def.jpg-resized",
        }

    def test_pathological_backslash_alt_is_linear(self):
        content = "![" + "\\" * 5000 + "x"
        start = time.perf_counter()
        assert extract_user_file_names(content) == set()
        assert strip_user_file_urls(content) == content
        assert time.perf_counter() - start < 0.5

    @pytest.mark.parametrize(
        "unit",
        ["![x](", "![x](a ", "![x][a_b.png](", "![x][a_b.png](a ", "![[[", "[" * 8],
    )
    def test_unterminated_destinations_are_linear(self, unit):
        def run(n):
            content = unit * n
            start = time.perf_counter()
            strip_user_file_urls(content)
            append_user_file_urls(content)
            extract_user_file_names(content)
            return time.perf_counter() - start

        small, large = run(20_000), run(40_000)
        # Doubling the input must not quadruple the time. The floor absorbs noise.
        assert large < max(small * 3, 0.1)
        assert large < 1


class TestExternalImagesAreKept:
    @pytest.mark.parametrize(
        "content",
        [
            "before ![photo](https://example.com/p.jpg) after",
            '![a](https://e.com/a.png "title") ![b](my file.png)',
            "![logo][remote]\n\n[remote]: https://e.com/p.png",
            "![a ![b](https://e.com/b.png)](https://e.com/a.png)",
            "![x](javascript:alert(1))",
        ],
    )
    def test_strip_and_append_leave_external_images_untouched(self, content):
        assert strip_user_file_urls(content) == content
        assert append_user_file_urls(content) == content

    def test_only_user_file_references_are_resolved(self):
        content = "![a][abc_def.png] ![c](https://example.com/x.png)"
        assert append_user_file_urls(content).endswith(
            ") ![c](https://example.com/x.png)"
        )


class TestPatternsMatchTheFrontend:
    """
    The frontend only loads a URL where the backend would have replaced it, so a
    character that ends a name or a line on one side but not the other would let a
    stored foreign URL through. These characters are whitespace in Python but not in
    JavaScript, or the other way around.
    """

    @pytest.mark.parametrize("char", ["\x1c", "\x1f", "\x85", "\u2028", "\ufeff"])
    def test_non_ascii_whitespace_is_part_of_the_name(self, char):
        content = f"![a][abc_def.png{char}](https://e.com/p.png)"
        assert strip_user_file_urls(content) == f"![a][abc_def.png{char}]"
        assert extract_user_file_names(content) == {f"abc_def.png{char}"}

    @pytest.mark.parametrize("char", ["\x1c", "\u2028", "\ufeff"])
    def test_non_ascii_whitespace_is_part_of_the_url(self, char):
        content = f"![a][abc_def.png](https://e.com/p{char}.png)"
        assert strip_user_file_urls(content) == "![a][abc_def.png]"

    @pytest.mark.parametrize("char", ["\r", "\x1c", "\u2028"])
    def test_only_newline_ends_a_line(self, char):
        content = f"x{char}```\n![a][abc_def.png](https://e.com/p.png)"
        assert list(iter_code_segments(content)) == [(content, False)]
        assert strip_user_file_urls(content) == f"x{char}```\n![a][abc_def.png]"

    @pytest.mark.parametrize("char", ["\x1c", "\u2028", "\ufeff"])
    def test_only_spaces_and_tabs_may_follow_a_closing_fence(self, char):
        content = f"```\ncode\n```{char}\n![a][abc_def.png](https://e.com/p.png)"
        assert list(iter_code_segments(content)) == [(content, True)]


class TestCountImageReferences:
    # Same cases as `countImageReferences` in richTextImageUtils.spec.js.
    @pytest.mark.parametrize(
        "content,expected",
        [
            (None, 0),
            ("", 0),
            (f"![a][{NAME}]", 1),
            (f"![a][{NAME}] ![a][{NAME}]", 2),
            (f"![a][{NAME}](https://h/x.png)", 1),
            (f"`![a][{NAME}]` ![b][{NAME}]", 1),
            (f"```\n![a][{NAME}]\n```\n![b][{NAME}]", 1),
            (f"x\r```\n![a][{NAME}]", 1),
            (f"!\\[a][{NAME}]", 0),
            (f"![a\\]b][{NAME}]", 1),
            (f"![a][{NAME}\u2028]", 1),
            ("![a](https://e.com/p.png)", 0),
        ],
    )
    def test_matches_the_frontend(self, content, expected):
        assert count_image_references(content) == expected


class TestEscapeUserFileReferences:
    def test_escapes_only_the_given_names(self):
        other = "abc_def.png"
        content = f"![a][{NAME}] ![b][{other}] `![c][{NAME}]` ![d][{NAME}](http://h/x)"
        escaped = escape_user_file_references(content, {NAME})
        assert escaped == (
            f"!\\[a][{NAME}] ![b][{other}] `![c][{NAME}]` !\\[d][{NAME}](http://h/x)"
        )
        assert extract_user_file_names(escaped) == {other}
        assert escape_user_file_references(content, set()) == content

    def test_escapes_references_outside_code(self):
        content = "![a][abc_def.png] `![b][abc_def.png]` ![c][abc_def.png](http://h/x)"
        escaped = escape_user_file_references(content)
        assert escaped == (
            "!\\[a][abc_def.png] `![b][abc_def.png]` !\\[c][abc_def.png](http://h/x)"
        )
        assert extract_user_file_names(escaped) == set()
        assert strip_user_file_urls(escaped) == escaped
        assert escape_user_file_references(escaped) == escaped

    def test_keeps_everything_else(self):
        content = "![x](https://e.com/p.png) [link](x)"
        assert escape_user_file_references(content) == content
        assert escape_user_file_references(None) is None


class TestReplaceUserFileImagesWithAlt:
    def test_returns_empty_string_for_none(self):
        assert replace_user_file_images_with_alt(None) == ""

    def test_replaces_reference_with_alt(self):
        content = "see ![my photo][abc_def.png] here"
        assert replace_user_file_images_with_alt(content) == "see my photo here"

    def test_replaces_reference_with_url_with_alt(self):
        content = "see ![my photo][abc_def.png](https://s/abc_def.png) here"
        assert replace_user_file_images_with_alt(content) == "see my photo here"

    def test_unescapes_brackets_in_alt(self):
        content = r"![a\[1\]][abc_def.png]"
        assert replace_user_file_images_with_alt(content) == "a[1]"

    def test_empty_alt_is_dropped(self):
        assert replace_user_file_images_with_alt("x ![][abc_def.png] y") == "x  y"

    def test_keeps_external_images(self):
        content = "![ext](https://a.b/c.png)"
        assert replace_user_file_images_with_alt(content) == content


class TestIsRenderableUserFile:
    def test_image_is_renderable(self):
        assert is_renderable_user_file(
            SimpleNamespace(is_image=True, original_extension="png")
        )

    def test_svg_is_renderable_even_when_not_flagged_as_image(self):
        for ext in ("svg", "SVG", "svgz"):
            assert is_renderable_user_file(
                SimpleNamespace(is_image=False, original_extension=ext)
            )

    def test_other_files_are_not_renderable(self):
        for ext in ("pdf", "html", "png", ""):
            assert not is_renderable_user_file(
                SimpleNamespace(is_image=False, original_extension=ext)
            )


class TestIterCodeSegments:
    def test_no_code(self):
        assert list(iter_code_segments("plain text")) == [("plain text", False)]

    def test_inline_span(self):
        assert list(iter_code_segments("a `b` c")) == [
            ("a ", False),
            ("`b`", True),
            (" c", False),
        ]

    def test_span_closes_on_same_length_run_only(self):
        # A double backtick opens; the single backtick inside does not close it.
        assert list(iter_code_segments("``a ` b`` c")) == [
            ("``a ` b``", True),
            (" c", False),
        ]

    def test_unclosed_backtick_is_text(self):
        assert list(iter_code_segments("a ` b")) == [("a ` b", False)]

    def test_fenced_block(self):
        content = "before\n```\n![x][a_b.png]\n```\nafter"
        assert list(iter_code_segments(content)) == [
            ("before\n", False),
            ("```\n![x][a_b.png]\n```\n", True),
            ("after", False),
        ]

    def test_tilde_fence_and_longer_closing(self):
        content = "~~~\ncode\n~~~~\nafter"
        assert list(iter_code_segments(content)) == [
            ("~~~\ncode\n~~~~\n", True),
            ("after", False),
        ]

    def test_fence_not_closed_by_other_char_or_shorter_run(self):
        content = "````\n~~~\n```\nstill code"
        assert list(iter_code_segments(content)) == [(content, True)]

    def test_unclosed_fence_runs_to_end(self):
        content = "text\n```\nnever closed"
        assert list(iter_code_segments(content)) == [
            ("text\n", False),
            ("```\nnever closed", True),
        ]

    def test_pathological_backtick_runs_are_linear(self):
        # Runs of distinct lengths never pair up, so every run is scanned once.
        content = " ".join("`" * n for n in range(1, 2000))
        start = time.monotonic()
        segments = list(iter_code_segments(content))
        assert time.monotonic() - start < 1
        assert segments == [(content, False)]


class TestCodeIsLiteral:
    REF = "![x][abc_def.png]"

    def test_extract_ignores_inline_code_and_fences(self):
        content = f"`{self.REF}` and\n```\n{self.REF}\n```\n![y][real_one.png]"
        assert extract_user_file_names(content) == {"real_one.png"}

    def test_count_ignores_code(self):
        assert count_image_references(f"`{self.REF}` {self.REF}") == 1

    def test_strip_and_append_ignore_code(self):
        resolved = f"{self.REF}(http://h/abc_def.png)"
        assert strip_user_file_urls(f"`{resolved}` {resolved}") == (
            f"`{resolved}` {self.REF}"
        )
        appended = append_user_file_urls(f"`{self.REF}` {self.REF}")
        assert appended.startswith(f"`{self.REF}` {self.REF}(")

    def test_replace_with_alt_ignores_code(self):
        assert replace_user_file_images_with_alt(f"`{self.REF}` {self.REF}") == (
            f"`{self.REF}` x"
        )

    def test_keep_first_ignores_code(self):
        content = f"`{self.REF}` {self.REF} {self.REF}"
        assert keep_first_image_references(content, 1) == f"`{self.REF}` {self.REF} x"

    def test_reference_split_by_code_span_does_not_match(self):
        assert extract_user_file_names("![x`]`[abc_def.png]") == set()
