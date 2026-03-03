"""
Eval: verify the agent can create rows with all managed field types.

Sets up a table with text, long_text, number, boolean, date, datetime,
single_select, multiple_select, and link_row fields, then asks the agent
to create 5 rows with sample data.

Run with: pytest -m eval -k test_eval_database_rows -v -s

Configuration (via environment variables):
- EVAL_LLM_MODEL: The model to use (default: "groq:openai/gpt-oss-120b")
- GROQ_API_KEY / OPENAI_API_KEY: Required depending on the model
"""

import pytest

from baserow.contrib.database.rows.handler import RowHandler

from .eval_utils import (
    assert_no_tool_errors,
    build_database_ui_context,
    create_eval_assistant,
    print_message_history,
)

# ---------------------------------------------------------------------------
# Eval prompts — one per test, easy to scan for coverage
# ---------------------------------------------------------------------------

PROMPT_CREATES_ROWS_WITH_ALL_FIELD_TYPES = (
    "Create 5 rows with diverse sample data in table {table_name}. "
    "Fill in ALL fields with realistic values."
)


def _create_rich_table(data_fixture):
    """
    Create a table with all managed field types plus a linked table
    with sample data.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    # Linked table (target for link_row fields)
    linked_table = data_fixture.create_database_table(
        database=database, name="Categories"
    )
    linked_primary = data_fixture.create_text_field(
        table=linked_table, name="Name", primary=True
    )

    # Populate linked table with sample rows
    RowHandler().force_create_rows(
        user,
        linked_table,
        [
            {linked_primary.db_column: "Work"},
            {linked_primary.db_column: "Personal"},
            {linked_primary.db_column: "Urgent"},
        ],
    )

    # Main table with all managed field types
    table = data_fixture.create_database_table(database=database, name="Tasks")
    title = data_fixture.create_text_field(table=table, name="Title", primary=True)
    description = data_fixture.create_long_text_field(table=table, name="Description")
    estimated_hours = data_fixture.create_number_field(
        table=table, name="Estimated Hours", number_decimal_places=1
    )
    completed = data_fixture.create_boolean_field(table=table, name="Completed")
    due_date = data_fixture.create_date_field(table=table, name="Due Date")
    created_at = data_fixture.create_date_field(
        table=table, name="Created At", date_include_time=True
    )

    status_field = data_fixture.create_single_select_field(table=table, name="Status")
    data_fixture.create_select_option(field=status_field, value="To Do", order=0)
    data_fixture.create_select_option(field=status_field, value="In Progress", order=1)
    data_fixture.create_select_option(field=status_field, value="Done", order=2)

    tags_field = data_fixture.create_multiple_select_field(table=table, name="Tags")
    data_fixture.create_select_option(field=tags_field, value="Bug", order=0)
    data_fixture.create_select_option(field=tags_field, value="Feature", order=1)
    data_fixture.create_select_option(field=tags_field, value="Docs", order=2)

    category_field = data_fixture.create_link_row_field(
        table=table,
        link_row_table=linked_table,
        name="Category",
        link_row_multiple_relationships=False,
    )
    related_categories_field = data_fixture.create_link_row_field(
        table=table,
        link_row_table=linked_table,
        name="Related Categories",
        link_row_multiple_relationships=True,
    )

    return {
        "user": user,
        "workspace": workspace,
        "database": database,
        "table": table,
        "linked_table": linked_table,
        "fields": {
            "title": title,
            "description": description,
            "estimated_hours": estimated_hours,
            "completed": completed,
            "due_date": due_date,
            "created_at": created_at,
            "status": status_field,
            "tags": tags_field,
            "category": category_field,
            "related_categories": related_categories_field,
        },
    }


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_rows_with_all_field_types(data_fixture, eval_model, db):
    """
    Agent should create rows with sensible data for every field type.

    This tests the full flow:
    1. Agent calls get_tables_schema to learn the table structure
    2. Agent calls load_row_tools to unlock create_rows_in_table_X
    3. Agent calls create_rows_in_table_X with all fields populated
    """

    res = _create_rich_table(data_fixture)
    user = res["user"]
    workspace = res["workspace"]
    database = res["database"]
    table = res["table"]
    fields = res["fields"]

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=20, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database, table=table)
    deps.tool_helpers.request_context["ui_context"] = ui_context

    result = agent.run_sync(
        user_prompt=PROMPT_CREATES_ROWS_WITH_ALL_FIELD_TYPES.format(
            table_name=table.name
        ),
        deps=deps,
        model=model,
        usage_limits=usage_limits,
        toolsets=[toolset],
    )

    print_message_history(result)

    # No tool errors or validation retries
    assert_no_tool_errors(tracker, result)

    # Verify rows were created
    table_model = table.get_model()
    row_count = table_model.objects.count()
    assert row_count == 5, f"Expected 5 rows, got {row_count}"

    # Verify every field type is populated in at least some rows
    sample_rows = table_model.objects.all()

    def _get_field_value(row, field_name):
        return getattr(row, fields[field_name].db_column, None)

    field_checks = {
        "title": lambda r: bool(_get_field_value(r, "title")),
        "description": lambda r: bool(_get_field_value(r, "description")),
        "estimated_hours": lambda r: _get_field_value(r, "estimated_hours") is not None,
        "completed": lambda r: _get_field_value(r, "completed") is not None,
        "due_date": lambda r: _get_field_value(r, "due_date") is not None,
        "created_at": lambda r: _get_field_value(r, "created_at") is not None,
        "status": lambda r: _get_field_value(r, "status").value
        in ["To Do", "In Progress", "Done"],
        "tags": lambda r: set(
            _get_field_value(r, "tags").values_list("value", flat=True)
        )
        & {"Bug", "Feature", "Docs"},
        "category": lambda r: len(_get_field_value(r, "category").all()),
        "related_categories": lambda r: len(
            _get_field_value(r, "related_categories").all()
        )
        > 0,
    }
    for field_name, check_fn in field_checks.items():
        matches = [r for r in sample_rows if check_fn(r)]
        assert matches, f"No rows had valid data for field '{field_name}'"
