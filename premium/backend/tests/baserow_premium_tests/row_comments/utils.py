from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from django.contrib.auth.models import AbstractUser

from baserow.contrib.database.models import Database
from baserow.contrib.database.table.models import Table
from baserow.core.tools import ToolContext
from baserow_premium.row_comments.models import RowComment
from baserow_premium.row_comments.tools import search_row_comments

DAY_1 = datetime(2026, 1, 10, 12, tzinfo=timezone.utc)


@dataclass
class CommentScenario:
    ctx: ToolContext
    bob: AbstractUser
    database: Database
    projects: Table
    tasks: Table
    project_rows: list[Any]
    task_rows: list[Any]
    comments: list[RowComment]


def create_comment(
    author: AbstractUser,
    row: Any,
    text: str,
    mentions: tuple[AbstractUser, ...] | list[AbstractUser] = (),
    day: int = 1,
) -> RowComment:
    """
    :param author: Who wrote the comment.
    :param row: The row it is on.
    :param text: Its text, followed by the mentions.
    :param mentions: The users it mentions.
    :param day: The day it was written at noon UTC, counted from ``DAY_1``.
    :return: The comment.
    """

    content = [{"type": "text", "text": text}]
    for mentioned in mentions:
        content += [
            {"type": "text", "text": " "},
            {
                "type": "mention",
                "attrs": {"id": mentioned.id, "label": mentioned.first_name},
            },
        ]
    comment = RowComment.objects.create(
        user=author,
        table=row.get_parent(),
        row_id=row.id,
        message={"type": "doc", "content": [{"type": "paragraph", "content": content}]},
    )
    comment.mentions(manager="objects_and_identities").set(mentions)
    created_on = DAY_1 + timedelta(days=day - 1)
    RowComment.objects.filter(id=comment.id).update(
        created_on=created_on, updated_on=created_on
    )
    comment.refresh_from_db()
    return comment


def create_comment_scenario(fixture: Any, **user_kwargs: Any) -> CommentScenario:
    """
    A database with four comments, one a day: Anna's and Bob's on Projects, then
    Bob's and Anna's on Tasks. Anna searches.

    :param fixture: The data fixture of the edition under test.
    :param user_kwargs: How Anna is created.
    :return: The scenario.
    """

    anna = fixture.create_user(first_name="Anna", **user_kwargs)
    bob = fixture.create_user(first_name="Bob")
    workspace = fixture.create_workspace(users=[anna, bob])
    database = fixture.create_database_application(workspace=workspace)
    projects, _, project_rows = fixture.build_table(
        user=anna,
        database=database,
        name="Projects",
        columns=[("Name", {"type": "text", "primary": True})],
        rows=[["Acme"], ["Globex"]],
    )
    tasks, _, task_rows = fixture.build_table(
        user=anna,
        database=database,
        name="Tasks",
        columns=[("Name", {"type": "text", "primary": True})],
        rows=[["Call"], ["Mail"]],
    )
    comments = [
        create_comment(anna, project_rows[0], "Check", [bob], day=1),
        create_comment(bob, project_rows[1], "Done", [anna], day=2),
        create_comment(bob, task_rows[0], "Later", day=3),
        create_comment(anna, task_rows[1], "Both", [anna, bob], day=4),
    ]
    return CommentScenario(
        ToolContext(user=anna, workspace=workspace),
        bob,
        database,
        projects,
        tasks,
        project_rows,
        task_rows,
        comments,
    )


def found_comments(scenario: CommentScenario, **arguments: Any) -> list[int]:
    """
    :param scenario: The scenario to search.
    :param arguments: The search's arguments, after the database.
    :return: The numbers of the scenario's comments the search returns, counted
        from 1 in the order they were written, as the search orders them.
    """

    ids = [comment.id for comment in scenario.comments]
    result = search_row_comments(scenario.ctx, scenario.database.id, **arguments)
    return [ids.index(comment["id"]) + 1 for comment in result["comments"]]
