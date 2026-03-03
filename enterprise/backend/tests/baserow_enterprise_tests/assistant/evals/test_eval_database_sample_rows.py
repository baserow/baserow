"""
Eval: verify that create_tables generates sample rows automatically.

These tests ask the agent to create tables WITHOUT saying "Don't add sample
rows", so the default ``add_sample_rows=True`` path is exercised.

Run with: pytest -m eval -k test_eval_database_sample_rows -v -s

Configuration (via environment variables):
- EVAL_LLM_MODEL: The model to use (default: "groq:openai/gpt-oss-120b")
- GROQ_API_KEY / OPENAI_API_KEY: Required depending on the model
"""

import pytest

from baserow.contrib.database.models import Table

from .eval_utils import (
    assert_no_tool_errors,
    build_database_ui_context,
    create_eval_assistant,
    print_message_history,
)

# ---------------------------------------------------------------------------
# Eval prompts — one per test, easy to scan for coverage
# (NOTE: intentionally NOT saying "Don't add sample rows")
# ---------------------------------------------------------------------------

PROMPT_CREATE_TABLE_WITH_SAMPLE_ROWS = (
    "Create a Recipes table in database {database_name} with these fields: "
    "Name (text), Description (long text), "
    "Prep Time in Minutes (number), Servings (number), "
    "and Vegetarian (boolean)."
)

PROMPT_CREATE_RELATED_TABLES_WITH_SAMPLE_ROWS = (
    "Set up the Bookstore database {database_name} with: "
    "1. An Authors table with Name and Bio. "
    "2. A Books table with Title, Genre "
    "(single select: Fiction, Non-Fiction, Science, History), "
    "Price, and a link to the Authors table."
)


def _run_agent(
    agent, deps, tracker, model, usage_limits, toolset, question, ui_context
):
    """Helper to run the agent with standard configuration."""
    deps.tool_helpers.request_context["ui_context"] = ui_context

    result = agent.run_sync(
        user_prompt=question,
        deps=deps,
        model=model,
        usage_limits=usage_limits,
        toolsets=[toolset],
    )
    return result


# ---------------------------------------------------------------------------
# Single table with basic fields + sample rows
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_create_table_with_sample_rows(data_fixture, eval_model):
    """
    Agent creates a simple table and sample rows are automatically
    generated (add_sample_rows defaults to True).
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Cooking"
    )

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=20, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATE_TABLE_WITH_SAMPLE_ROWS.format(
            database_name=database.name
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    # Verify the table was created
    tables = Table.objects.filter(database=database)
    recipe_tables = [t for t in tables if "recipe" in t.name.lower()]
    assert len(recipe_tables) == 1, (
        f"Expected 1 Recipes table, got {len(recipe_tables)}: "
        f"{[t.name for t in tables]}"
    )

    table = recipe_tables[0]

    # Verify sample rows were created
    table_model = table.get_model()
    row_count = table_model.objects.count()
    assert row_count >= 3, (
        f"Expected at least 3 sample rows in Recipes, got {row_count}. "
        f"Sample row generation likely failed."
    )

    # Spot-check that the primary field is populated
    primary_field = table.get_primary_field().specific
    rows = list(table_model.objects.all()[:5])
    non_empty = [r for r in rows if getattr(r, primary_field.db_column, "")]
    assert len(non_empty) >= 3, (
        f"Expected at least 3 rows with a non-empty primary field, got {len(non_empty)}"
    )


# ---------------------------------------------------------------------------
# Two related tables with sample rows
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_create_related_tables_with_sample_rows(data_fixture, eval_model):
    """
    Agent creates two related tables (Authors → Books) and sample rows
    are generated for both, including link_row references.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Bookstore"
    )

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=25, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATE_RELATED_TABLES_WITH_SAMPLE_ROWS.format(
            database_name=database.name
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    tables = Table.objects.filter(database=database)
    table_names = {t.name.lower(): t for t in tables}

    # Verify both tables exist
    author_tables = [name for name in table_names if "author" in name]
    book_tables = [name for name in table_names if "book" in name]

    assert len(author_tables) >= 1, (
        f"Expected an Authors table, got: {list(table_names.keys())}"
    )
    assert len(book_tables) >= 1, (
        f"Expected a Books table, got: {list(table_names.keys())}"
    )

    # Verify Authors has sample rows
    authors_table = table_names[author_tables[0]]
    authors_model = authors_table.get_model()
    authors_count = authors_model.objects.count()
    assert authors_count >= 3, (
        f"Expected at least 3 sample rows in Authors, got {authors_count}. "
        f"Sample row generation likely failed."
    )

    # Verify Books has sample rows
    books_table = table_names[book_tables[0]]
    books_model = books_table.get_model()
    books_count = books_model.objects.count()
    assert books_count >= 3, (
        f"Expected at least 3 sample rows in Books, got {books_count}. "
        f"Sample row generation likely failed."
    )
