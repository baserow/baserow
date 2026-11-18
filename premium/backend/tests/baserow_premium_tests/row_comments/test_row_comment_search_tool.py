"""Tests for the tool that searches the row comments of a database."""

from datetime import datetime, timedelta, timezone

from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest
from baserow_premium_tests.row_comments.utils import (
    DAY_1,
    create_comment,
    create_comment_scenario,
    found_comments,
)

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.models import Table
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.tools.errors import ToolInputError
from baserow_premium.license.exceptions import FeaturesNotAvailableError
from baserow_premium.row_comments.models import RowComment
from baserow_premium.row_comments.tools import search_row_comments


@pytest.fixture(autouse=True)
def debug_licences(settings):
    # `has_active_premium_license` only works in debug mode.
    settings.DEBUG = True


@pytest.fixture
def scenario(premium_data_fixture):
    return create_comment_scenario(
        premium_data_fixture, has_active_premium_license=True
    )


@pytest.mark.django_db
def test_search_returns_the_comments_of_every_table_newest_first(scenario):
    result = search_row_comments(scenario.ctx, scenario.database.id)

    assert [comment["id"] for comment in result["comments"]] == [
        comment.id for comment in reversed(scenario.comments)
    ]
    assert result["has_more"] is False
    assert result["comments"][0] == {
        "id": scenario.comments[3].id,
        "table_id": scenario.tasks.id,
        "table": "Tasks",
        "row_id": scenario.task_rows[1].id,
        "row": "Mail",
        "user_id": scenario.ctx.user.id,
        "user_name": "Anna",
        "text": "Both @Anna @Bob",
        "mentions": [
            {"id": scenario.ctx.user.id, "name": "Anna"},
            {"id": scenario.bob.id, "name": "Bob"},
        ],
        "created_on": scenario.comments[3].created_on.isoformat(),
        "edited": False,
    }


@pytest.mark.django_db
def test_search_finds_comments_by_who_they_mention(scenario):
    bob_id = scenario.bob.id

    assert found_comments(scenario, mentioned_users=[bob_id]) == [4, 1]
    assert found_comments(scenario, mentioned_users=[str(bob_id)]) == [4, 1]
    assert found_comments(scenario, mentioned_users=["bo"]) == [4, 1]
    # 0 is the user the tools act as, and a comment mentioning both is found once.
    assert found_comments(scenario, mentioned_users=[0]) == [4, 2]
    assert found_comments(scenario, mentioned_users=[0, "Bob"]) == [4, 2, 1]
    with pytest.raises(ToolInputError):
        found_comments(scenario, mentioned_users=["Carl"])


@pytest.mark.django_db
def test_search_finds_comments_by_author_and_date(scenario):
    day_2 = DAY_1 + timedelta(days=1)

    assert found_comments(scenario, authors=["Bob"]) == [3, 2]
    assert found_comments(scenario, authors=[0], created_after=day_2) == [4]
    # From the start of day 2 up to, but not including, the start of day 4.
    assert found_comments(
        scenario,
        created_after=datetime(2026, 1, 11, tzinfo=timezone.utc),
        created_before=datetime(2026, 1, 13, tzinfo=timezone.utc),
    ) == [3, 2]


@pytest.mark.django_db
def test_search_reads_a_date_without_timezone_in_the_context_timezone(scenario):
    # Day 1's comment is written at 12:00 UTC, which is 13:00 in Rome.
    dates = {
        "created_after": datetime(2026, 1, 10, 12, 30),
        "created_before": datetime(2026, 1, 11),
    }

    assert found_comments(scenario, **dates) == []
    scenario.ctx.timezone = "Europe/Rome"
    assert found_comments(scenario, **dates) == [1]


@pytest.mark.django_db
def test_search_limits_to_the_given_tables_and_pages(scenario):
    arguments = {"table_ids": [scenario.tasks.id], "size": 1}

    first = search_row_comments(scenario.ctx, scenario.database.id, **arguments)

    assert [comment["id"] for comment in first["comments"]] == [scenario.comments[3].id]
    assert first["has_more"] is True
    assert found_comments(scenario, page=2, **arguments) == [3]
    assert found_comments(scenario, page=3, **arguments) == []


@pytest.mark.django_db
def test_search_skips_trashed_comments_and_comments_on_trashed_rows(scenario):
    RowHandler().delete_row_by_id(
        scenario.ctx.user, scenario.projects, scenario.project_rows[0].id
    )
    RowComment.objects.filter(id=scenario.comments[2].id).update(trashed=True)

    assert found_comments(scenario) == [4, 2]


@pytest.mark.django_db
def test_search_only_reaches_the_tables_of_the_database(scenario, premium_data_fixture):
    other = create_comment_scenario(
        premium_data_fixture, has_active_premium_license=True
    )
    # A member of both workspaces, searching from the first.
    premium_data_fixture.create_user_workspace(
        user=scenario.ctx.user, workspace=other.ctx.workspace
    )
    elsewhere = premium_data_fixture.create_database_table(
        user=scenario.ctx.user,
        database=premium_data_fixture.create_database_application(
            workspace=scenario.ctx.workspace
        ),
    )

    with pytest.raises(ApplicationDoesNotExist):
        search_row_comments(scenario.ctx, other.database.id)
    for table in (other.tasks, elsewhere):
        with pytest.raises(Table.DoesNotExist):
            found_comments(scenario, table_ids=[scenario.tasks.id, table.id])


@pytest.mark.django_db
def test_search_needs_premium(premium_data_fixture):
    scenario = create_comment_scenario(premium_data_fixture)

    with pytest.raises(FeaturesNotAvailableError):
        search_row_comments(scenario.ctx, scenario.database.id)


@pytest.mark.django_db
def test_search_runs_the_same_queries_however_many_comments_there_are(scenario):
    def count_queries() -> int:
        with CaptureQueriesContext(connection) as queries:
            search_row_comments(scenario.ctx, scenario.database.id, size=100)
        return len(queries)

    # The first search also fills the caches of the tables' models.
    count_queries()
    few = count_queries()
    for day in range(5, 25):
        create_comment(
            scenario.bob, scenario.project_rows[1], "More", [scenario.bob], day
        )

    assert count_queries() == few
