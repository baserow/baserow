from unittest.mock import Mock

import pytest

from baserow.contrib.database.search.handler import SearchHandler, SearchMode


def test_escape_query():
    # Spacing is standardized.
    assert SearchHandler.escape_query("Full   text   search") == "Full text search"
    # Escape colons for URLs.
    assert SearchHandler.escape_query("https://baserow.io") == "https baserow io"
    # Special characters are trimmed.
    assert SearchHandler.escape_query("Base<&(|)!>row") == "Base row"
    # Leading or trailing spaces trimmed.
    assert SearchHandler.escape_query("  Full text search  ") == "Full text search"


@pytest.mark.django_db
def test_get_default_search_mode_for_table_with_workspace_search_data(data_fixture):
    table = data_fixture.create_database_table()

    assert (
        SearchHandler.get_default_search_mode_for_table(table)
        == SearchMode.FT_WITH_COUNT
    )


@pytest.mark.django_db
def test_get_default_search_mode_for_table_with_tsvectors_for_templates():
    mock_table = Mock()
    mock_table.database = Mock()

    mock_table.database.workspace = Mock()
    mock_table.database.workspace.has_template = lambda: True

    assert (
        SearchHandler.get_default_search_mode_for_table(mock_table) == SearchMode.COMPAT
    )


def test_escape_postgres_query_with_per_token_wildcard():
    # Doesn't attempt to match the current search
    assert (
        SearchHandler.escape_postgres_query("french cuisi", True)
        == "$$french$$:* <-> $$cuisi$$:*"
    )


def test_escape_postgres_query_without_per_token_wildcard():
    # Attempts to match the current search as closely as possible
    assert (
        SearchHandler.escape_postgres_query("french cuisi", False)
        == "$$french$$ <-> $$cuisi$$:*"
    )
