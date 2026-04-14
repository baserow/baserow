import re

import pytest

# Skip: one-time legacy migration test that requires cwd=changelog/ and
# mutates the real filesystem. The markdown-to-JSON migration is complete.
pytestmark = pytest.mark.skip(reason="legacy converter test requires cwd=changelog/ and mutates the filesystem")


def get_unique_tokens_from_file(file):
    tokens = set()
    for line in file:
        words = re.split(" |_", line)

        words_sanitised = [
            "".join(e for e in word if e.isalnum()).lower() for word in words
        ]

        tokens = tokens.union(set(words_sanitised))
    return tokens


def test_token_match():
    from _pytest.fixtures import fixture  # noqa: F401
    from changelog_legacy_converter import main  # noqa: F401

    from changelog import purge, release  # noqa: F401

    legacy_changelog = open("../changelog.md", "r")

    # Make sure everything is deleted first
    purge()

    # Generate the changelog json files
    main()

    # Make a release to generate the changelog.md
    release("Add", "./src")

    changelog = open("./src/changelog.md", "r")

    tokens_to_ignore = {"unreleased"}

    tokens_legacy = get_unique_tokens_from_file(legacy_changelog).union(
        tokens_to_ignore
    )
    tokens_generated = get_unique_tokens_from_file(changelog).union(tokens_to_ignore)

    assert tokens_legacy == tokens_generated


# Note: commented out for now since we need some more sanitising to make this
# test work properly
# def test_lines_match():
#     # Load the generated changelog
#     generated_changelog = open("changelog.md", "r")
#
#     assert set(generated_changelog.readlines()) == set(legacy_changelog.readlines())
