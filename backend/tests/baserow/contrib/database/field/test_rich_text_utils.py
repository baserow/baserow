from baserow.contrib.database.fields.rich_text_utils import (
    append_user_file_urls,
    extract_user_file_names,
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
