import time
from types import SimpleNamespace

from baserow.contrib.database.fields.rich_text_utils import (
    append_user_file_urls,
    extract_user_file_names,
    is_renderable_user_file,
    replace_user_file_images_with_alt,
    resolve_user_file_urls,
    strip_user_file_urls,
    validate_external_image_protocols,
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
        assert validate_external_image_protocols(content) == content
        assert time.perf_counter() - start < 0.5


class TestValidateExternalImageProtocols:
    def test_returns_empty_string_for_none(self):
        assert validate_external_image_protocols(None) == ""

    def test_returns_content_unchanged_without_images(self):
        assert validate_external_image_protocols("plain [link](x)") == "plain [link](x)"

    def test_preserves_https_image(self):
        content = "before ![photo](https://example.com/p.jpg) after"
        assert validate_external_image_protocols(content) == content

    def test_preserves_http_image(self):
        content = "![photo](http://example.com/p.jpg)"
        assert validate_external_image_protocols(content) == content

    def test_downgrades_data_uri_image_to_link(self):
        content = "![x](data:image/png;base64,AAAA)"
        assert (
            validate_external_image_protocols(content)
            == "[x](data:image/png;base64,AAAA)"
        )

    def test_downgrades_javascript_uri_to_link(self):
        content = "![x](javascript:alert(1))"
        assert validate_external_image_protocols(content) == "[x](javascript:alert(1))"

    def test_does_not_touch_user_file_references(self):
        content = (
            "![a][abc_def.png] ![b][abc_def.png](https://storage/abc_def.png) "
            "![c](https://example.com/x.png)"
        )
        assert validate_external_image_protocols(content) == content

    def test_handles_escaped_brackets_in_alt(self):
        content = r"![a\]b](https://example.com/x.png)"
        assert validate_external_image_protocols(content) == content

    def test_downgrades_ftp_to_link(self):
        content = "![x](ftp://example.com/x.png)"
        assert (
            validate_external_image_protocols(content) == "[x](ftp://example.com/x.png)"
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
