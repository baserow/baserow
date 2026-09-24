import time
from types import SimpleNamespace

import pytest

from baserow.contrib.database.fields.rich_text_utils import (
    MAX_INLINE_IMAGE_SCAN_COST,
    append_user_file_urls,
    contains_markdown_image,
    count_image_references,
    demote_external_images_to_links,
    extract_user_file_names,
    is_renderable_user_file,
    iter_code_segments,
    keep_first_image_references,
    neutralize_markdown_images,
    normalize_rich_text_for_storage,
    replace_user_file_images_with_alt,
    resolve_user_file_urls,
    strip_user_file_urls,
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
        assert demote_external_images_to_links(content) == content
        assert time.perf_counter() - start < 0.5

    @pytest.mark.parametrize(
        "unit",
        ["![x](", "![x](a ", "![x][a_b.png](", "![x][a_b.png](a ", "![[[", "[" * 8],
    )
    def test_unterminated_destinations_are_linear(self, unit):
        def run(n):
            content = unit * n
            start = time.perf_counter()
            normalize_rich_text_for_storage(content)
            strip_user_file_urls(content)
            extract_user_file_names(content)
            contains_markdown_image(content)
            return time.perf_counter() - start

        small, large = run(20_000), run(40_000)
        # Doubling the input must not quadruple the time. The floor absorbs noise.
        assert large < max(small * 3, 0.1)
        assert large < 1


class TestDemoteExternalImagesToLinks:
    def test_returns_empty_string_for_none(self):
        assert demote_external_images_to_links(None) == ""

    def test_returns_content_unchanged_without_images(self):
        assert demote_external_images_to_links("plain [link](x)") == "plain [link](x)"

    def test_demotes_https_image(self):
        content = "before ![photo](https://example.com/p.jpg) after"
        assert (
            demote_external_images_to_links(content)
            == "before [photo](https://example.com/p.jpg) after"
        )

    def test_demotes_http_image(self):
        content = "![photo](http://example.com/p.jpg)"
        assert (
            demote_external_images_to_links(content)
            == "[photo](http://example.com/p.jpg)"
        )

    def test_downgrades_data_uri_image_to_link(self):
        content = "![x](data:image/png;base64,AAAA)"
        assert (
            demote_external_images_to_links(content)
            == "[x](data:image/png;base64,AAAA)"
        )

    def test_downgrades_javascript_uri_to_link(self):
        content = "![x](javascript:alert(1))"
        assert demote_external_images_to_links(content) == "[x](javascript:alert(1))"

    def test_demotes_image_with_title_or_spaces(self):
        assert (
            demote_external_images_to_links(
                '![a](https://e.com/a.png "title") ![b](my file.png)'
            )
            == '[a](https://e.com/a.png "title") [b](my file.png)'
        )

    def test_does_not_touch_user_file_references(self):
        content = (
            "![a][abc_def.png] ![b][abc_def.png](https://storage/abc_def.png) "
            "![c](https://example.com/x.png)"
        )
        assert demote_external_images_to_links(content) == (
            "![a][abc_def.png] ![b][abc_def.png](https://storage/abc_def.png) "
            "[c](https://example.com/x.png)"
        )

    def test_handles_escaped_brackets_in_alt(self):
        content = r"![a\]b](https://example.com/x.png)"
        assert (
            demote_external_images_to_links(content)
            == r"[a\]b](https://example.com/x.png)"
        )

    @pytest.mark.parametrize(
        "content",
        [
            "![a](https://x.com/p.png)",
            "![a][abc_def.png]",
            "![a][abc_def.png](https://s/abc_def.png)",
            "text ![a](x) ![b][cd_ef.png] end",
            "![](https://x.com/p.png)",
            r"![a\]b](https://x.com/p.png)",
            "[a](https://x.com/p.png)",
        ],
    )
    def test_is_idempotent(self, content):
        """Stored values pass through this on every save, so a second run must
        not keep rewriting them."""

        once = demote_external_images_to_links(content)
        assert demote_external_images_to_links(once) == once

    def test_downgrades_ftp_to_link(self):
        content = "![x](ftp://example.com/x.png)"
        assert (
            demote_external_images_to_links(content) == "[x](ftp://example.com/x.png)"
        )


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

    def test_replaces_external_images_with_alt(self):
        content = "![ext](https://a.b/c.png)"
        assert replace_user_file_images_with_alt(content) == "ext"

    def test_replaces_external_image_empty_alt(self):
        content = "x ![](https://a.b/c.png) y"
        assert replace_user_file_images_with_alt(content) == "x  y"


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

    def test_indented_code_block(self):
        content = "text\n\n    ![x](https://e.com/a.png)\n\nafter"
        assert list(iter_code_segments(content)) == [
            ("text\n\n", False),
            ("    ![x](https://e.com/a.png)\n", True),
            ("\nafter", False),
        ]
        assert normalize_rich_text_for_storage(content) == content

    def test_fence_inside_list_item(self):
        content = "- item\n\n  ```\n  ![x](https://e.com/a.png)\n  ```\n"
        assert normalize_rich_text_for_storage(content) == content

    def test_indented_continuation_is_not_code(self):
        content = "para\n    ![x](https://e.com/a.png)"
        assert normalize_rich_text_for_storage(content) == (
            "para\n    [x](https://e.com/a.png)"
        )

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
    EXT = "![x](https://e.com/a.png)"

    def test_extract_ignores_inline_code_and_fences(self):
        content = f"`{self.REF}` and\n```\n{self.REF}\n```\n![y][real_one.png]"
        assert extract_user_file_names(content) == {"real_one.png"}

    def test_count_ignores_code(self):
        assert count_image_references(f"`{self.REF}` {self.REF}") == 1

    def test_demote_ignores_code(self):
        content = f"`{self.EXT}` {self.EXT}"
        assert demote_external_images_to_links(content) == (
            f"`{self.EXT}` [x](https://e.com/a.png)"
        )

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


class TestNormalizeRichTextForStorage:
    def test_empty(self):
        assert normalize_rich_text_for_storage(None) == ""
        assert normalize_rich_text_for_storage("") == ""

    def test_strips_urls_and_demotes_external(self):
        assert (
            normalize_rich_text_for_storage(
                "![a][abc_def.png](http://h/abc_def.png) ![b](https://e.com/b.png)"
            )
            == "![a][abc_def.png] [b](https://e.com/b.png)"
        )

    def test_is_idempotent(self):
        value = "![a][abc_def.png] [b](https://e.com/b.png) `![c](http://x)`"
        assert normalize_rich_text_for_storage(value) == value


class TestContainsMarkdownImage:
    @pytest.mark.parametrize(
        "content",
        [
            None,
            "",
            "text",
            "![a][abc_def.png] text",
            "`![x](https://e.com/p.png)`",
            "```\n![x](https://e.com/p.png)\n```",
            "para\n\n    ![x](https://e.com/p.png)",
            "\\![x](https://e.com/p.png)",
            # A definition only matters when an image uses its label.
            "![a][abc_def.png]\n\n[other]: https://e.com/p.png",
        ],
    )
    def test_no_image(self, content):
        assert not contains_markdown_image(content)

    @pytest.mark.parametrize(
        "content",
        [
            "![x](https://e.com/p.png)",
            # Tracking pixel through a reference definition.
            "![logo][remote]\n\n[remote]: https://e.com/p.png",
            "![logo]\n\n[logo]: https://e.com/p.png",
            "![a][r]\n\n> [r]: https://e.com/p.png",
            "- ![a][r]\n- [r]: https://e.com/p.png",
            "|a|\n|-|\n|![x][r]|\n\n[r]: https://e.com/p.png",
            # A definition hijacking a user file name, case-insensitively.
            "![a][abc_def.png]\n\n[ABC_def.PNG]: https://e.com/p.png",
            # Nested alt: the inner image is foreign.
            "![a ![b](https://e.com/p.png)][abc_def.png]",
            # An autolink ends before the backtick that looks like a code span.
            "<http://a`b>![x](https://e.com/p.png)`c",
        ],
    )
    def test_image(self, content):
        assert contains_markdown_image(content)

    def test_over_budget_counts_as_image(self):
        content = "`![x]` " + "[" * MAX_INLINE_IMAGE_SCAN_COST
        start = time.perf_counter()
        assert contains_markdown_image(content)
        assert time.perf_counter() - start < 0.5

    def test_budget_ignores_paragraphs_without_foreign_images(self):
        paragraph = "![a][abc_def.png] " + "[x] " * 1000
        content = "\n\n".join([paragraph] * 100)
        assert not contains_markdown_image(content)


class TestNeutralizeMarkdownImages:
    def test_keeps_content_without_images(self):
        value = "![a][abc_def.png] [b](https://e.com/b.png) `![c](http://x)`"
        assert neutralize_markdown_images(value) == value

    def test_escapes_pixel_reference(self):
        value = "![logo][remote]\n\n[remote]: https://e.com/p.png"
        assert neutralize_markdown_images(value) == (
            "\\![logo][remote]\n\n[remote]: https://e.com/p.png"
        )

    def test_escapes_hijacking_definition_and_keeps_reference(self):
        value = "![a][abc_def.png]\n\n> [ABC_def.png]: https://e.com/p.png"
        result = neutralize_markdown_images(value)
        assert result == "![a][abc_def.png]\n\n> \\[ABC_def.png]: https://e.com/p.png"
        assert extract_user_file_names(result) == {"abc_def.png"}

    def test_escapes_nested_alt(self):
        result = neutralize_markdown_images(
            "![a ![b](https://e.com/p.png)][abc_def.png]"
        )
        assert not contains_markdown_image(result)

    def test_escapes_code_as_last_resort(self):
        value = "<http://a`b>![x](https://e.com/p.png)`c"
        result = neutralize_markdown_images(value)
        assert result == "<http://a`b>\\![x](https://e.com/p.png)`c"
        assert not contains_markdown_image(result)

    @pytest.mark.parametrize(
        "value",
        [
            "![x](https://e.com/p.png)",
            "![logo][remote]\n\n[remote]: https://e.com/p.png",
            "![a][abc_def.png]\n\n[abc_def.png]: https://e.com/p.png",
        ],
    )
    def test_is_idempotent(self, value):
        once = neutralize_markdown_images(value)
        assert not contains_markdown_image(once)
        assert neutralize_markdown_images(once) == once
